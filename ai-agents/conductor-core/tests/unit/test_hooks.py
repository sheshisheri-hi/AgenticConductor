"""Tests for Conductor hooks system (ADR-012)."""

import pytest
import json
import tempfile
from pathlib import Path
from conductor_core.hooks import (
    HookEvent, HookType, HookConfig, HookPayload, HookMatcher,
    HookEngine, HookResult, PolicyResolver, PolicyMergeRule
)


class TestHookMatcher:
    """Tests for HookMatcher."""
    
    def test_matcher_matches_agent_name(self):
        """Test agent name matching."""
        matcher = HookMatcher(agent_name="code_agent")
        assert matcher.matches(agent_name="code_agent")
        assert not matcher.matches(agent_name="notify_agent")
    
    def test_matcher_matches_stage_name(self):
        """Test stage name matching with regex."""
        matcher = HookMatcher(stage_name="^(code|deploy).*")
        assert matcher.matches(stage_name="code_generation")
        assert matcher.matches(stage_name="deploy_patch")
        assert not matcher.matches(stage_name="notify")
    
    def test_matcher_matches_all_fields(self):
        """Test matching on all fields."""
        matcher = HookMatcher(agent_name="code_agent", source="snyk")
        assert matcher.matches(agent_name="code_agent", source="snyk")
        assert not matcher.matches(agent_name="code_agent", source="ado")
    
    def test_matcher_no_matcher_matches_all(self):
        """Test that empty matcher matches everything."""
        matcher = HookMatcher()
        assert matcher.matches()
        assert matcher.matches(agent_name="any", stage_name="any", source="any")


class TestHookConfig:
    """Tests for HookConfig."""
    
    def test_command_hook_validation(self):
        """Test command hook requires bash field."""
        with pytest.raises(ValueError, match="bash"):
            HookConfig(type=HookType.COMMAND)
    
    def test_http_hook_validation(self):
        """Test HTTP hook requires url field."""
        with pytest.raises(ValueError, match="url"):
            HookConfig(type=HookType.HTTP)
    
    def test_inject_hook_validation(self):
        """Test inject hook requires context field."""
        with pytest.raises(ValueError, match="context"):
            HookConfig(type=HookType.INJECT)
    
    def test_command_hook_creation(self):
        """Test creating valid command hook."""
        hook = HookConfig(
            type=HookType.COMMAND,
            bash="echo test",
            timeout_sec=10
        )
        assert hook.type == HookType.COMMAND
        assert hook.bash == "echo test"
        assert hook.timeout_sec == 10


class TestHookPayload:
    """Tests for HookPayload."""
    
    def test_payload_to_dict(self):
        """Test converting payload to dict."""
        payload = HookPayload(
            run_id="run-123",
            timestamp=1000000,
            workflow_name="test-workflow",
            mode="plan",
            source="snyk",
            agent_name="test_agent"
        )
        
        data = payload.to_dict()
        assert data["run_id"] == "run-123"
        assert data["agent_name"] == "test_agent"
        assert "confidence" not in data  # None values excluded
    
    def test_payload_with_all_fields(self):
        """Test payload with all optional fields."""
        payload = HookPayload(
            run_id="run-123",
            timestamp=1000000,
            workflow_name="test",
            mode="execute",
            source="ado",
            agent_name="code_agent",
            confidence=0.95,
            tokens_used=1000
        )
        
        data = payload.to_dict()
        assert data["confidence"] == 0.95
        assert data["tokens_used"] == 1000


class TestHookEngine:
    """Tests for HookEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create HookEngine instance."""
        return HookEngine()
    
    def test_load_hooks_from_dict(self, engine):
        """Test loading hooks from configuration dict."""
        hooks_config = {
            "runStart": [
                {
                    "type": "http",
                    "url": "https://example.com/hooks"
                }
            ],
            "preAgentRun": [
                {
                    "type": "command",
                    "bash": "echo test",
                    "matcher": {"agentName": "code_agent"}
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        
        assert HookEvent.RUN_START in engine.hooks
        assert HookEvent.PRE_AGENT_RUN in engine.hooks
        assert len(engine.hooks[HookEvent.RUN_START]) == 1
        assert len(engine.hooks[HookEvent.PRE_AGENT_RUN]) == 1
    
    def test_fire_http_hook_fail_open(self, engine):
        """Test HTTP hook is fail-open (always succeeds)."""
        hooks_config = {
            "runEnd": [
                {
                    "type": "http",
                    "url": "https://invalid.example.com/hooks"  # Will fail
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        payload = HookPayload(
            run_id="run-1",
            timestamp=1000,
            workflow_name="test",
            mode="plan",
            source="snyk"
        )
        
        # Should not raise (fail-open)
        results = engine.fire(HookEvent.RUN_END, payload)
        assert len(results) == 1
        assert results[0].success  # Even though HTTP fails, hook succeeds
    
    def test_fire_command_hook_success(self, engine):
        """Test successful command hook execution."""
        hooks_config = {
            "runStart": [
                {
                    "type": "command",
                    "bash": "echo 'Hook executed successfully'"
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        payload = HookPayload(
            run_id="run-1",
            timestamp=1000,
            workflow_name="test",
            mode="plan",
            source="snyk"
        )
        
        results = engine.fire(HookEvent.RUN_START, payload)
        assert len(results) == 1
        assert results[0].success
    
    def test_fire_command_hook_fail_closed_raises(self, engine):
        """Test fail-closed hook raises on failure."""
        hooks_config = {
            "preAgentRun": [
                {
                    "type": "command",
                    "bash": "exit 1"  # Command fails
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        payload = HookPayload(
            run_id="run-1",
            timestamp=1000,
            workflow_name="test",
            mode="plan",
            source="snyk",
            agent_name="test_agent"
        )
        
        # Should raise because preAgentRun is fail-closed
        with pytest.raises(ValueError, match="blocked"):
            engine.fire(HookEvent.PRE_AGENT_RUN, payload)
    
    def test_matcher_filters_hooks(self, engine):
        """Test hook matcher filters execution."""
        hooks_config = {
            "preAgentRun": [
                {
                    "type": "command",
                    "bash": "echo 'Should not run'",
                    "matcher": {"agentName": "code_agent"}
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        payload = HookPayload(
            run_id="run-1",
            timestamp=1000,
            workflow_name="test",
            mode="plan",
            source="snyk",
            agent_name="notify_agent"  # Different agent
        )
        
        results = engine.fire(HookEvent.PRE_AGENT_RUN, payload)
        # Should return empty because matcher filtered it out
        assert len(results) == 0
    
    def test_inject_hook(self, engine):
        """Test inject hook returns context."""
        hooks_config = {
            "preAgentRun": [
                {
                    "type": "inject",
                    "context": "POLICY: No destructive changes"
                }
            ]
        }
        
        engine.load_hooks(hooks_config)
        payload = HookPayload(
            run_id="run-1",
            timestamp=1000,
            workflow_name="test",
            mode="plan",
            source="snyk"
        )
        
        results = engine.fire(HookEvent.PRE_AGENT_RUN, payload)
        assert len(results) == 1
        assert "POLICY" in results[0].output


class TestPolicyResolver:
    """Tests for PolicyResolver."""
    
    @pytest.fixture
    def resolver(self):
        """Create PolicyResolver instance."""
        return PolicyResolver()
    
    @pytest.fixture
    def temp_policies(self):
        """Create temporary policy files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Project policy
            project_policy = {
                "name": "test-project",
                "strict": True,
                "integrations": ["snyk"],
                "confidence_threshold": 0.7
            }
            project_file = tmppath / "project.json"
            project_file.write_text(json.dumps(project_policy))
            
            # User policy
            user_policy = {
                "strict": False,
                "integrations": ["ado"],
                "confidence_threshold": 0.8
            }
            user_file = tmppath / "user.json"
            user_file.write_text(json.dumps(user_policy))
            
            yield {"project": project_file, "user": user_file}
    
    def test_load_single_policy(self, resolver, temp_policies):
        """Test loading single policy."""
        assert resolver.load_policy(temp_policies["project"], "project")
        assert len(resolver.policies) == 1
    
    def test_load_multiple_policies(self, resolver, temp_policies):
        """Test loading multiple policies."""
        assert resolver.load_policy(temp_policies["project"], "project")
        assert resolver.load_policy(temp_policies["user"], "user")
        assert len(resolver.policies) == 2
    
    def test_resolve_most_restrictive(self, resolver, temp_policies):
        """Test most-restrictive merge strategy."""
        resolver.load_policy(temp_policies["project"], "project")
        resolver.load_policy(temp_policies["user"], "user")
        
        result = resolver.resolve()
        
        # strict is most_restrictive: True OR False = True
        assert result["strict"] is True
    
    def test_resolve_merge_list(self, resolver, temp_policies):
        """Test merge_list strategy."""
        resolver.load_policy(temp_policies["project"], "project")
        resolver.load_policy(temp_policies["user"], "user")
        
        result = resolver.resolve()
        
        # integrations is merge_list: [snyk, ado]
        assert set(result["integrations"]) == {"snyk", "ado"}
    
    def test_resolve_first_wins(self, resolver, temp_policies):
        """Test first_wins strategy."""
        resolver.load_policy(temp_policies["project"], "project")
        resolver.load_policy(temp_policies["user"], "user")
        
        result = resolver.resolve()
        
        # name is first_wins: keep project name
        assert result["name"] == "test-project"
    
    def test_detect_conflicts(self, resolver, temp_policies):
        """Test conflict detection."""
        resolver.load_policy(temp_policies["project"], "project")
        resolver.load_policy(temp_policies["user"], "user")
        
        conflicts = resolver.check_conflicts()
        
        # Should detect conflicts in strict and confidence_threshold
        assert "strict" in conflicts or "confidence_threshold" in conflicts
    
    def test_register_custom_rule(self, resolver):
        """Test registering custom merge rule."""
        rule = PolicyMergeRule("custom_field", "merge_list")
        resolver.register_rule(rule)
        
        assert "custom_field" in resolver.rules
        assert resolver.rules["custom_field"].merge_strategy == "merge_list"
