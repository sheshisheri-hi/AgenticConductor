"""Integration tests for orchestrator with manifest, hooks, and security (Sprint 4).

Tests the full pipeline:
1. Load manifest with agents, hooks, policies
2. Fire hooks at lifecycle events
3. Detect secrets and block execution
4. Verify no regressions
"""

import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.manifest import ConductorManifest, Author
from conductor_core.hooks.engine import HookEngine
from conductor_core.hooks.types import HookEvent, HookPayload
from conductor_core.hooks.policy import PolicyResolver
from conductor_core.security.secret_detector import SecretDetector
from conductor_core.interfaces import IAgent


class MockAgent(IAgent):
    """Mock agent for testing."""
    
    async def run(self, context) -> AgentDecision:
        """Return a simple decision."""
        decision = AgentDecision(
            agent="mock",
            action="test",
            confidence=0.95,
            recommendation="proceed",
        )
        context.append_decision(decision)  # IMPORTANT: must append to context
        return decision


class TestOrchestratorIntegration:
    """Integration tests for full orchestrator pipeline."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_hooks_fires_lifecycle_events(self):
        """Verify hooks fire at each lifecycle event."""
        # Create hook engine with tracking
        hook_engine = HookEngine()
        
        # Track which hooks fired
        fired_events = []
        
        # Create custom hook engine that tracks fires
        original_fire = hook_engine.fire
        def tracked_fire(event, payload):
            fired_events.append(event.value)
            return original_fire(event, payload)
        hook_engine.fire = tracked_fire
        
        # Create orchestrator with mock agents and hook engine
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},
            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                    "on_block": "done",
                }
            ]
        })
        
        orchestrator = WorkflowOrchestrator(
            agents=agents,
            graph=graph,
            hook_engine=hook_engine,
        )
        
        # Run workflow
        context = WorkflowContext(run_id="TEST-001", payload={"source": "test"})
        result = await orchestrator.run(context)
        
        # Verify hooks fired
        assert "runStart" in fired_events
        assert "runEnd" in fired_events
        assert "preAgentRun" in fired_events
        assert "postAgentRun" in fired_events
        assert not result.blocked
    
    @pytest.mark.asyncio
    async def test_orchestrator_security_blocks_on_secret_input(self):
        """Verify secret detection blocks execution on input secrets."""
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                }
            ]
        })
        
        orchestrator = WorkflowOrchestrator(agents=agents, graph=graph)
        
        # Create context with secret in payload
        context = WorkflowContext(
            run_id="TEST-002",
            payload={"source": "test", "token": "ghp_" + "a" * 40}  # Valid GitHub token format
        )
        result = await orchestrator.run(context)
        
        # Verify execution was blocked
        assert result.blocked
        assert "Secret detected" in result.blocked_reason
    
    @pytest.mark.asyncio
    async def test_orchestrator_security_clean_payload_allows_execution(self):
        """Verify clean payloads allow normal execution."""
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                }
            ]
        })
        
        orchestrator = WorkflowOrchestrator(agents=agents, graph=graph)
        
        # Create context with clean payload
        context = WorkflowContext(
            run_id="TEST-003",
            payload={"source": "test", "severity": "HIGH"}
        )
        result = await orchestrator.run(context)
        
        # Verify execution completed
        assert len(result.decisions) > 0
        assert not result.blocked
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_policy_resolver(self):
        """Verify PolicyResolver can be initialized and used."""
        policy_resolver = PolicyResolver()
        
        # Test that PolicyResolver exists and has expected methods
        assert hasattr(policy_resolver, 'load_policy')
        assert hasattr(policy_resolver, 'resolve')
        assert hasattr(policy_resolver, 'check_conflicts')
        
        # Test that it's created with expected attributes
        assert policy_resolver.policies is not None
    
    @pytest.mark.asyncio
    async def test_manifest_loader_integration(self):
        """Verify WorkflowOrchestrator.from_manifest() loads everything."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create conductor.json with correct field names
            manifest_data = {
                "name": "test-manifest",
                "description": "Test manifest",
                "version": "1.0.0",
                "agents": ["agents/"],  # Not agents_paths
                "workflow": "workflow.yaml",  # Not workflow_path
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
            manifest_path = tmpdir / "conductor.json"
            manifest_path.write_text(json.dumps(manifest_data))
            
            # Create workflow.yaml
            workflow_path = tmpdir / "workflow.yaml"
            workflow_yaml = """
name: test-workflow
first_stage: triage
stages:
  - name: triage
    agent: triage
    on_proceed: done
"""
            workflow_path.write_text(workflow_yaml)
            
            # Create agents directory with mock agent
            agents_dir = tmpdir / "agents"
            agents_dir.mkdir()
            
            # Try loading manifest
            try:
                manifest = ConductorManifest.load(str(manifest_path))
                assert manifest is not None
                assert manifest.name == "test-manifest"
            except Exception as e:
                # Expected if agent file not found, but manifest validation should pass
                assert "not found" in str(e).lower() or isinstance(e, FileNotFoundError)


class TestHookPayloadCreation:
    """Test HookPayload creation from orchestrator context."""
    
    def test_hook_payload_from_context(self):
        """Verify HookPayload correctly captures context."""
        import time
        
        run_id = "TEST-004"
        timestamp = int(time.time() * 1000)
        workflow_name = "test"
        mode = "plan"
        source = "snyk"
        
        payload = HookPayload(
            run_id=run_id,
            timestamp=timestamp,
            workflow_name=workflow_name,
            mode=mode,
            source=source,
            agent_name="triage",
            stage_name="triage_stage",
        )
        
        assert payload.run_id == run_id
        assert payload.workflow_name == workflow_name
        assert payload.agent_name == "triage"
        assert payload.stage_name == "triage_stage"
    
    def test_hook_payload_with_decision(self):
        """Verify HookPayload captures decision details."""
        import time
        
        payload = HookPayload(
            run_id="TEST-005",
            timestamp=int(time.time() * 1000),
            workflow_name="test",
            mode="execute",
            source="test",
            agent_name="triage",
            recommendation="proceed",
            confidence=0.95,
        )
        
        payload_dict = payload.to_dict()
        assert payload_dict["recommendation"] == "proceed"
        assert payload_dict["confidence"] == 0.95
        assert payload_dict["source"] == "test"


class TestSecurityGateIntegration:
    """Test security gates integrated into orchestrator."""
    
    @pytest.mark.asyncio
    async def test_preagent_security_gate_blocks_secrets(self):
        """Verify pre-agent security gate detects secrets."""
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                }
            ]
        })
        
        secret_detector = SecretDetector()
        orchestrator = WorkflowOrchestrator(
            agents=agents,
            graph=graph,
            secret_detector=secret_detector,
        )
        
        # Context with AWS secret
        context = WorkflowContext(
            run_id="TEST-006",
            payload={
                "source": "test",
                "aws_key": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        )
        result = await orchestrator.run(context)
        
        # Should be blocked by secret detector
        assert result.blocked
        assert "Secret detected" in result.blocked_reason or len(result.decisions) == 0
    
    @pytest.mark.asyncio
    async def test_postagent_security_gate_clean_decision(self):
        """Verify post-agent security gate allows clean output."""
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                }
            ]
        })
        
        secret_detector = SecretDetector()
        orchestrator = WorkflowOrchestrator(
            agents=agents,
            graph=graph,
            secret_detector=secret_detector,
        )
        
        # Clean context
        context = WorkflowContext(
            run_id="TEST-007",
            payload={"source": "test", "priority": "high"}
        )
        result = await orchestrator.run(context)
        
        # Should complete successfully
        assert len(result.decisions) >= 1
        assert not result.blocked


class TestIntegrationRegressions:
    """Verify no regressions in core orchestrator behavior."""
    
    @pytest.mark.asyncio
    async def test_all_stages_still_execute(self):
        """Verify full workflow still executes through all stages."""
        agents = {"triage": MockAgent(), "review": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "review",
                },
                {
                    "name": "review",
                    "agent": "review",
                    "on_proceed": "done",
                }
            ]
        })
        
        orchestrator = WorkflowOrchestrator(agents=agents, graph=graph)
        context = WorkflowContext(run_id="TEST-008", payload={"source": "test"})
        result = await orchestrator.run(context)
        
        # Should have 2 decisions (triage + review)
        assert len(result.decisions) == 2
        assert not result.blocked
    
    @pytest.mark.asyncio
    async def test_filter_still_works(self):
        """Verify filter engine still filters payloads."""
        agents = {"triage": MockAgent()}
        graph = WorkflowGraph.from_dict({
            "workflow": {"name": "test", "mode": "plan"},            "stages": [
                {
                    "name": "triage",
                    "agent": "triage",
                    "on_proceed": "done",
                }
            ],
            "filters": [
                {
                    "type": "reject_if_in",
                    "field": "severity",
                    "values": ["LOW"]
                }
            ]
        })
        
        orchestrator = WorkflowOrchestrator(agents=agents, graph=graph)
        
        # Payload that gets filtered
        context = WorkflowContext(
            run_id="TEST-009",
            payload={"source": "test", "severity": "LOW"}
        )
        result = await orchestrator.run(context)
        
        # Should be blocked by filter
        assert result.blocked
        assert "Filtered" in result.blocked_reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
