"""BaseAgent — LLM-calling agent with multi-round enrichment loop.

Migrated and generalized from Coding-Agent's base_agent.py.
All LLM-using agents inherit from BaseAgent.

Key changes from the original:
- Uses WorkflowContext instead of PipelineContext
- No hardcoded domain fields (payload: dict only)
- Token count is real (tracked in TelemetryData)
- Prompts dir resolved from subclass location
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from string import Template

import structlog

from conductor_core.config.settings import settings
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.exceptions import AgentExecutionError, LLMCallError, LLMParseError
from conductor_core.interfaces import IAgent, ILLMProvider

logger = structlog.get_logger(__name__)


class BaseAgent(IAgent):
    """Base class for all LLM-using agents.

    Provides:
    - Prompt loading from .md files with $variable substitution
    - LLM calling via ILLMProvider (injected, never direct SDK)
    - Response parsing to AgentDecision (with JSON fence stripping)
    - Multi-round enrichment loop with configurable max rounds
    - Token tracking via context.telemetry
    """

    AGENT_NAME: str = "base"
    CONFIDENCE_THRESHOLD: float = settings.confidence_threshold
    MAX_ROUNDS: int = settings.max_enrichment_rounds

    # Per-agent model override.  Set as a class variable in subclasses to use a
    # specific model instead of the global settings.llm_model.  Useful for
    # adversarial / review agents that should run against a *different* model
    # than the agents that produced the artefacts they are reviewing.
    #
    # Examples:
    #   class ReviewerAgent(BaseAgent):
    #       MODEL_OVERRIDE = "o1-preview"   # adversarial — different from planner
    #
    # The YAML stage field  model:  is a *runtime* override that takes priority
    # over this class-level value.  Resolution order (highest → lowest):
    #   1. _runtime_model  (set by orchestrator from YAML stage.model)
    #   2. MODEL_OVERRIDE  (class-level constant)
    #   3. settings.llm_model  (global env setting)
    MODEL_OVERRIDE: str | None = None

    def __init__(
        self,
        llm_provider: ILLMProvider,
        prompts_dir: Path | str | None = None,
    ) -> None:
        """Initialize with an LLM provider.

        Args:
            llm_provider: ILLMProvider implementation (mock or real).
            prompts_dir: Override the default prompts directory.
                         Defaults to <subclass_file_location>/prompts/
        """
        self._llm = llm_provider
        self._last_call_latency_ms: float = 0.0
        # Orchestrator may set this at runtime from the YAML stage `model:` field.
        self._runtime_model: str | None = None
        if prompts_dir is not None:
            self._prompts_dir = Path(prompts_dir)
        else:
            # Subclass is responsible for setting the correct prompts_dir
            # via this default (resolved relative to subclass module file)
            self._prompts_dir = Path(__file__).parent / "prompts"

    def _resolve_model(self) -> str:
        """Return the model to use for this call.

        Priority: runtime YAML stage override > class MODEL_OVERRIDE > global setting.
        """
        return self._runtime_model or self.MODEL_OVERRIDE or settings.llm_model

    def _load_prompt(self, name: str, **variables: str) -> str:
        """Load prompt template from disk and substitute variables.

        Args:
            name: Prompt file name without .md extension.
            **variables: Template variables to substitute.

        Returns:
            Rendered prompt string.

        Raises:
            AgentExecutionError: If prompt file not found.
        """
        prompt_path = self._prompts_dir / f"{name}.md"
        if not prompt_path.exists():
            raise AgentExecutionError(
                self.AGENT_NAME,
                message=f"Prompt file not found: {prompt_path}",
            )
        template = Template(prompt_path.read_text(encoding="utf-8"))
        return template.safe_substitute(**variables)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        context: WorkflowContext,
    ) -> tuple[str, str]:
        """Call LLM provider, track tokens and latency in telemetry.

        Args:
            system_prompt: System role prompt.
            user_prompt: User role prompt.
            context: WorkflowContext for telemetry recording.

        Returns:
            Tuple of (raw_response, model_used).

        Raises:
            LLMCallError: If the LLM call fails.
        """
        model = self._resolve_model()
        # Estimate input tokens (4 chars ≈ 1 token — actual counted on response)
        input_tokens_est = (len(system_prompt) + len(user_prompt)) // 4
        logger.info(
            "llm_call_started",
            agent=self.AGENT_NAME,
            run_id=context.run_id,
            model=model,
            input_tokens_est=input_tokens_est,
        )

        start = time.monotonic()
        try:
            response = await self._llm.call(system_prompt, user_prompt, model=model)
        except Exception as e:
            logger.error(
                "llm_call_failed",
                agent=self.AGENT_NAME,
                run_id=context.run_id,
                error=str(e),
            )
            raise LLMCallError(self.AGENT_NAME, cause=e) from e

        latency_ms = (time.monotonic() - start) * 1000
        self._last_call_latency_ms = latency_ms
        # Count actual output tokens
        output_tokens = len(response) // 4
        total_tokens = input_tokens_est + output_tokens

        context.telemetry.record_llm_call(
            agent=self.AGENT_NAME,
            tokens=total_tokens,
            latency_ms=latency_ms,
        )

        logger.info(
            "llm_call_complete",
            agent=self.AGENT_NAME,
            run_id=context.run_id,
            model=model,
            response_len=len(response),
            tokens=total_tokens,
            latency_ms=round(latency_ms, 1),
        )
        return response, model

    def _parse_decision(self, raw_response: str, round_num: int) -> AgentDecision:
        """Parse raw LLM response into an AgentDecision."""
        try:
            cleaned = self._strip_code_fences(raw_response)
            data = json.loads(cleaned, strict=False)
            return AgentDecision(
                agent=self.AGENT_NAME,
                action=data.get("action", "analyze"),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", []),
                evidence=data.get("evidence", []),
                concerns=data.get("concerns", []),
                recommendation=data.get("recommendation", "proceed"),
                requires_human=data.get("requires_human", False),
                round=round_num,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            if raw_response and raw_response.strip():
                logger.warning(
                    "llm_response_not_json",
                    agent=self.AGENT_NAME,
                    preview=raw_response[:120],
                )
                return AgentDecision(
                    agent=self.AGENT_NAME,
                    action="review",
                    confidence=0.0,
                    reasoning=[f"LLM returned plain text: {raw_response[:300]}"],
                    evidence=[],
                    concerns=["Non-JSON response — human review required"],
                    recommendation="block",
                    requires_human=True,
                    round=round_num,
                )
            raise LLMParseError(
                self.AGENT_NAME,
                raw_response=raw_response,
                message=f"Failed to parse LLM response: {e}",
            ) from e

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Extract JSON from LLM response — handles code fences and embedded JSON."""
        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            end_idx = next(
                (i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"),
                None,
            )
            candidate = "\n".join(lines[1:end_idx]).strip() if end_idx else "\n".join(lines[1:]).strip()
            if candidate:
                return candidate

        # Brace-depth scan for first top-level {...} block
        depth = 0
        start = None
        for i, ch in enumerate(cleaned):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    block = cleaned[start : i + 1]
                    try:
                        json.loads(block, strict=False)
                        return block
                    except json.JSONDecodeError:
                        start = None
        return cleaned

    def _get_prompt_variables(self, context: WorkflowContext, round_num: int) -> dict:
        """Get template variables for prompt rendering.

        Override in subclasses to inject domain-specific payload fields.
        Base implementation provides common variables available in all contexts.
        """
        return {
            "run_id": context.run_id,
            "mode": context.mode,
            "current_stage": context.current_stage,
            "prior_decisions": self._format_prior_decisions(context),
            "round": str(round_num),
        }

    def _format_prior_decisions(self, context: WorkflowContext) -> str:
        if not context.decisions:
            return "No prior decisions."
        parts = []
        for d in context.decisions:
            parts.append(
                f"- [{d.agent}] Round {d.round}: {d.recommendation} "
                f"(confidence: {d.confidence:.2f}) — {'; '.join(d.reasoning[:2])}"
            )
        return "\n".join(parts)

    def _system_prompt_name(self) -> str:
        return f"{self.AGENT_NAME}_system"

    def _user_prompt_name(self) -> str:
        return f"{self.AGENT_NAME}_user"

    async def _reason(self, context: WorkflowContext, round_num: int) -> AgentDecision:
        """Execute one reasoning round: load prompts → LLM → parse decision."""
        variables = self._get_prompt_variables(context, round_num)
        system_prompt = self._load_prompt(self._system_prompt_name(), **variables)
        user_prompt = self._load_prompt(self._user_prompt_name(), **variables)
        raw_response, model_used = await self._call_llm(system_prompt, user_prompt, context)
        decision = self._parse_decision(raw_response, round_num)

        decision.raw_llm_response = raw_response
        decision.prompt_system = system_prompt
        decision.prompt_user = user_prompt
        decision.model_used = model_used
        input_tokens = (len(system_prompt) + len(user_prompt)) // 4
        output_tokens = len(raw_response) // 4
        decision.tokens_used = input_tokens + output_tokens
        decision.estimated_cost_usd = (input_tokens * 5.0 + output_tokens * 15.0) / 1_000_000
        decision.latency_ms = self._last_call_latency_ms

        logger.info(
            "agent_decision",
            agent=self.AGENT_NAME,
            run_id=context.run_id,
            stage=context.current_stage,
            confidence=decision.confidence,
            recommendation=decision.recommendation,
            round=round_num,
        )
        return decision

    async def _enrich(self, context: WorkflowContext, concerns: list[str]) -> dict:
        """Fetch additional context based on concerns. Override in subclasses."""
        return {}

    async def run(self, context: WorkflowContext) -> AgentDecision:
        """Execute agent with multi-round enrichment loop."""
        logger.info("agent_started", agent=self.AGENT_NAME, run_id=context.run_id)
        return await self.run_with_enrichment(context)

    async def run_with_enrichment(self, context: WorkflowContext) -> AgentDecision:
        """Multi-round enrichment loop: reason → check confidence → enrich → repeat."""
        decision: AgentDecision | None = None
        try:
            for round_num in range(1, self.MAX_ROUNDS + 1):
                decision = await self._reason(context, round_num)
                context.append_decision(decision)

                if decision.confidence >= self.CONFIDENCE_THRESHOLD:
                    return decision

                if decision.wants_more_rounds():
                    enriched = await self._enrich(context, decision.concerns)
                    context.append_enrichment(enriched)
                    continue

                if decision.requires_human:
                    context.mark_blocked(
                        f"{self.AGENT_NAME}: requires human review — "
                        f"{'; '.join(decision.concerns)}"
                    )
                    return decision

                return decision

            # Exhausted rounds
            assert decision is not None
            context.mark_blocked(
                f"{self.AGENT_NAME}: max rounds ({self.MAX_ROUNDS}) exhausted "
                f"with confidence {decision.confidence:.2f}"
            )
            decision.requires_human = True
            return decision

        except LLMCallError as e:
            context.mark_blocked(f"{self.AGENT_NAME}: LLM call failed — {e}")
            raise AgentExecutionError(self.AGENT_NAME, cause=e) from e
        except LLMParseError as e:
            context.mark_blocked(f"{self.AGENT_NAME}: parse error — {e}")
            raise AgentExecutionError(self.AGENT_NAME, cause=e) from e
        except AgentExecutionError:
            raise
        except Exception as e:
            logger.critical("unexpected_agent_error", agent=self.AGENT_NAME, error=str(e))
            context.mark_blocked(f"{self.AGENT_NAME}: unexpected error — {e}")
            raise
