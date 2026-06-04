"""HookEngine: Executes hooks with fail-open/fail-closed semantics (ADR-012).

Implements structured hook lifecycle:
- Command hooks: run shell commands (fail-closed for preAgentRun)
- HTTP hooks: POST to webhooks (always fail-open)
- Inject hooks: prepend context to agent prompts
"""

import json
import logging
import subprocess
import requests
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from dataclasses import dataclass

from .types import HookEvent, HookType, HookConfig, HookPayload, HookMatcher

logger = logging.getLogger(__name__)


@dataclass
class HookResult:
    """Result of hook execution."""
    success: bool
    hook_type: HookType
    event: HookEvent
    message: str
    blocked: bool = False  # True if hook blocked execution
    output: Optional[str] = None


class HookEngine:
    """Executes hooks with proper fail-open/fail-closed semantics."""
    
    # Events where command hooks are fail-closed (must succeed)
    FAIL_CLOSED_EVENTS = {
        HookEvent.PRE_AGENT_RUN,
        HookEvent.HUMAN_GATE_REQUEST,
    }
    
    def __init__(self):
        self.hooks: Dict[HookEvent, List[HookConfig]] = {}
        self.results: List[HookResult] = []
    
    @staticmethod
    def _camel_to_snake_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert camelCase keys to snake_case.
        
        Args:
            data: Dict with potentially camelCase keys
            
        Returns:
            Dict with snake_case keys
        """
        def camel_to_snake(name: str) -> str:
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        
        result = {}
        for key, value in data.items():
            snake_key = camel_to_snake(key)
            if isinstance(value, dict):
                result[snake_key] = HookEngine._camel_to_snake_dict(value)
            else:
                result[snake_key] = value
        return result
    
    def load_hooks(self, hooks_data: Dict[str, Any]) -> None:
        """Load hooks from configuration dict.
        
        Args:
            hooks_data: Hooks dict with events as keys
        """
        for event_str, configs in hooks_data.items():
            try:
                event = HookEvent(event_str)
            except ValueError:
                logger.warning(f"Unknown hook event: {event_str}")
                continue
            
            hook_list = []
            for config_data in configs if isinstance(configs, list) else [configs]:
                try:
                    # Convert camelCase keys to snake_case
                    config_dict = self._camel_to_snake_dict(config_data.copy())
                    
                    matcher_data = config_dict.pop("matcher", None)
                    matcher = HookMatcher(**matcher_data) if matcher_data else None
                    
                    hook = HookConfig(
                        type=HookType(config_dict.pop("type")),
                        matcher=matcher,
                        **config_dict
                    )
                    hook_list.append(hook)
                except Exception as e:
                    logger.error(f"Error parsing hook config: {e}")
                    continue
            
            self.hooks[event] = hook_list
            logger.info(f"Loaded {len(hook_list)} hooks for {event.value}")
    
    def fire(self,
            event: HookEvent,
            payload: HookPayload) -> List[HookResult]:
        """Fire hooks for an event.
        
        Args:
            event: Hook event to fire
            payload: Event payload
            
        Returns:
            List of HookResult objects
            
        Raises:
            ValueError: If fail-closed hook fails and event is fail-closed
        """
        results = []
        hooks = self.hooks.get(event, [])
        
        if not hooks:
            logger.debug(f"No hooks registered for {event.value}")
            return results
        
        logger.info(f"Firing {len(hooks)} hook(s) for {event.value}")
        
        for hook in hooks:
            # Check matcher
            if hook.matcher:
                if not hook.matcher.matches(
                    agent_name=payload.agent_name or "",
                    stage_name=payload.stage_name or "",
                    source=payload.source
                ):
                    logger.debug(f"Hook matcher did not match, skipping")
                    continue
            
            # Execute hook
            if hook.type == HookType.COMMAND:
                result = self._execute_command_hook(event, hook, payload)
            elif hook.type == HookType.HTTP:
                result = self._execute_http_hook(event, hook, payload)
            elif hook.type == HookType.INJECT:
                result = self._execute_inject_hook(event, hook, payload)
            else:
                result = HookResult(False, hook.type, event, "Unknown hook type")
            
            results.append(result)
            
            # Check fail-closed semantics
            if not result.success and event in self.FAIL_CLOSED_EVENTS:
                result.blocked = True
                logger.error(f"Fail-closed hook failed: {result.message}")
                raise ValueError(f"Hook blocked execution: {result.message}")
        
        self.results.extend(results)
        return results
    
    def _execute_command_hook(self,
                             event: HookEvent,
                             hook: HookConfig,
                             payload: HookPayload) -> HookResult:
        """Execute command hook (shell command).
        
        Args:
            event: Hook event
            hook: Hook configuration
            payload: Event payload
            
        Returns:
            HookResult with execution details
        """
        try:
            # Prepare environment
            env = dict(hook.env)
            env["CONDUCTOR_RUN_ID"] = payload.run_id
            env["CONDUCTOR_WORKFLOW"] = payload.workflow_name
            env["CONDUCTOR_MODE"] = payload.mode
            env["CONDUCTOR_SOURCE"] = payload.source
            
            if payload.agent_name:
                env["CONDUCTOR_AGENT"] = payload.agent_name
            if payload.stage_name:
                env["CONDUCTOR_STAGE"] = payload.stage_name
            
            # Execute command
            logger.debug(f"Running command hook: {hook.bash}")
            result = subprocess.run(
                hook.bash,
                shell=True,
                env={**dict(os.environ), **env},
                capture_output=True,
                text=True,
                timeout=hook.timeout_sec
            )
            
            if result.returncode == 0:
                return HookResult(
                    True,
                    HookType.COMMAND,
                    event,
                    f"Command hook succeeded",
                    output=result.stdout
                )
            else:
                return HookResult(
                    False,
                    HookType.COMMAND,
                    event,
                    f"Command hook failed with exit code {result.returncode}: {result.stderr}"
                )
        
        except subprocess.TimeoutExpired:
            return HookResult(
                False,
                HookType.COMMAND,
                event,
                f"Command hook timeout after {hook.timeout_sec}s"
            )
        except Exception as e:
            return HookResult(
                False,
                HookType.COMMAND,
                event,
                f"Command hook error: {e}"
            )
    
    def _execute_http_hook(self,
                          event: HookEvent,
                          hook: HookConfig,
                          payload: HookPayload) -> HookResult:
        """Execute HTTP hook (webhook).
        
        Args:
            event: Hook event
            hook: Hook configuration
            payload: Event payload
            
        Returns:
            HookResult with execution details (always succeeds due to fail-open)
        """
        try:
            # Prepare headers
            headers = dict(hook.headers)
            headers.setdefault("Content-Type", "application/json")
            
            # POST payload as JSON
            logger.debug(f"Posting HTTP hook to {hook.url}")
            response = requests.post(
                hook.url,
                json=payload.to_dict(),
                headers=headers,
                timeout=hook.timeout_sec
            )
            
            # HTTP hooks are fail-open: always return success
            if response.status_code < 400:
                return HookResult(
                    True,
                    HookType.HTTP,
                    event,
                    f"HTTP hook posted successfully (status {response.status_code})"
                )
            else:
                # Log warning but don't fail
                logger.warning(f"HTTP hook returned {response.status_code}")
                return HookResult(
                    True,  # Still success due to fail-open
                    HookType.HTTP,
                    event,
                    f"HTTP hook returned {response.status_code} (fail-open, continuing)"
                )
        
        except requests.Timeout:
            # Fail-open: log and continue
            logger.warning(f"HTTP hook timeout after {hook.timeout_sec}s (fail-open)")
            return HookResult(
                True,  # Success due to fail-open
                HookType.HTTP,
                event,
                f"HTTP hook timeout (fail-open)"
            )
        except Exception as e:
            # Fail-open: log and continue
            logger.warning(f"HTTP hook error: {e} (fail-open)")
            return HookResult(
                True,  # Success due to fail-open
                HookType.HTTP,
                event,
                f"HTTP hook error: {e} (fail-open)"
            )
    
    def _execute_inject_hook(self,
                            event: HookEvent,
                            hook: HookConfig,
                            payload: HookPayload) -> HookResult:
        """Execute inject hook (prepend context).
        
        Args:
            event: Hook event
            hook: Hook configuration
            payload: Event payload
            
        Returns:
            HookResult with injected context
        """
        return HookResult(
            True,
            HookType.INJECT,
            event,
            f"Context injected: {len(hook.context)} chars",
            output=hook.context
        )
    
    def get_results(self, event: Optional[HookEvent] = None) -> List[HookResult]:
        """Get hook execution results.
        
        Args:
            event: Filter by event, or None for all
            
        Returns:
            List of HookResult objects
        """
        if event:
            return [r for r in self.results if r.event == event]
        return self.results
    
    def clear_results(self) -> None:
        """Clear stored results."""
        self.results = []
