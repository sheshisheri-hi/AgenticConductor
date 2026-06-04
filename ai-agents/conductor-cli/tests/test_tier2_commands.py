"""Tests for ADR-010 Tier 2 CLI commands (run, model, resume, diff)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import pytest

from conductor_cli.commands.run_command import WorkflowExecutor, run_command
from conductor_cli.commands.model_command import ModelInspector, model_command
from conductor_cli.commands.resume_command import RunRecovery, resume_command
from conductor_cli.commands.diff_command import ChangeDiffer, diff_command
from conductor_core.context import WorkflowContext
from conductor_core.result import WorkflowResult
from conductor_core.manifest import ConductorManifest
from click.testing import CliRunner


# ============================================================================
# CONDUCTOR RUN TESTS
# ============================================================================

class TestRunCommand:
    """Test conductor run command."""
    
    @pytest.mark.asyncio
    async def test_run_command_basic(self, tmp_path):
        """Test basic run execution."""
        manifest = tmp_path / "conductor.json"
        manifest.write_text(json.dumps({
            "version": "1.0",
            "workflows": {
                "test_workflow": {
                    "stages": {
                        "analyze": {"agent": "agent_1"},
                    }
                }
            }
        }))
        
        executor = WorkflowExecutor(str(manifest))
        payload = {"source": "test", "priority": "HIGH"}
        
        with patch("conductor_core.orchestrator.WorkflowOrchestrator.from_manifest") as mock_orch:
            mock_orch.return_value = AsyncMock(
                run=AsyncMock(return_value=WorkflowResult(
                    run_id="RUN-001",
                    workflow_name="test_workflow",
                    mode="execute",
                    blocked=False,
                    decisions=[]
                ))
            )
            
            result = await executor.run(payload)
            assert result["run_id"] == "RUN-001"
            assert result["blocked"] is False
            assert "decisions_count" in result
    
    @pytest.mark.asyncio
    async def test_run_command_blocked(self, tmp_path):
        """Test run that gets blocked."""
        manifest = tmp_path / "conductor.json"
        manifest.write_text(json.dumps({
            "version": "1.0",
            "workflows": {"test": {"stages": {}}}
        }))
        
        executor = WorkflowExecutor(str(manifest), mode="plan")
        
        with patch("conductor_core.orchestrator.WorkflowOrchestrator.from_manifest") as mock_orch:
            mock_orch.return_value = AsyncMock(
                run=AsyncMock(return_value=WorkflowResult(
                    run_id="RUN-002",
                    workflow_name="test",
                    blocked=True,
                    blocked_reason="Secret detected in input",
                    decisions=[]
                ))
            )
            
            result = await executor.run({"source": "github"})
            assert result["blocked"] is True
            assert "Secret detected" in result["blocked_reason"]
    
    @pytest.mark.asyncio
    async def test_run_command_missing_manifest(self, tmp_path):
        """Test error when manifest not found."""
        executor = WorkflowExecutor(str(tmp_path / "missing.json"))
        
        with pytest.raises(FileNotFoundError):
            await executor.run({"source": "test"})
    
    def test_run_command_cli_json_output(self):
        """Test CLI with JSON output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create minimal manifest
            manifest_path = "conductor.json"
            with open(manifest_path, "w") as f:
                json.dump({"version": "1.0", "workflows": {}}, f)
            
            payload_path = "payload.json"
            with open(payload_path, "w") as f:
                json.dump({"source": "test"}, f)
            
            with patch("conductor_cli.commands.run_command.WorkflowExecutor.run") as mock_run:
                mock_run.return_value = asyncio.coroutine(lambda: {
                    "run_id": "RUN-001",
                    "workflow": "test",
                    "mode": "execute",
                    "blocked": False,
                    "decisions_count": 2,
                    "decisions": [],
                    "total_tokens": 1200,
                    "latency_ms": 5.5,
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:01",
                })()
                
                result = runner.invoke(
                    run_command,
                    ["--manifest", manifest_path, "--payload", payload_path, "--output", "json"]
                )
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["run_id"] == "RUN-001"


# ============================================================================
# CONDUCTOR MODEL TESTS
# ============================================================================

class TestModelCommand:
    """Test conductor model command."""
    
    def test_model_get_current(self, tmp_path):
        """Test getting current active model."""
        manifest = tmp_path / "conductor.json"
        manifest.write_text(json.dumps({
            "version": "1.0",
            "metadata": {"active_model": "gpt-4o"},
            "workflows": {}
        }))
        
        inspector = ModelInspector(str(manifest))
        model = inspector.get_active_model()
        assert model == "gpt-4o"
    
    def test_model_set_model(self, tmp_path):
        """Test setting active model."""
        manifest = tmp_path / "conductor.json"
        manifest.write_text(json.dumps({
            "version": "1.0",
            "metadata": {},
            "workflows": {}
        }))
        
        inspector = ModelInspector(str(manifest))
        result = inspector.set_active_model("claude-3-opus")
        assert result is True
        assert inspector.get_active_model() == "claude-3-opus"
    
    def test_model_list_available(self):
        """Test listing available models."""
        inspector = ModelInspector()
        models = inspector.list_available_models()
        assert "gpt-4o" in models
        assert "claude-3-opus" in models
        assert len(models) >= 5
    
    def test_model_cli_current(self):
        """Test CLI --current flag."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            manifest_path = "conductor.json"
            with open(manifest_path, "w") as f:
                json.dump({
                    "version": "1.0",
                    "metadata": {"active_model": "gpt-4o"},
                    "workflows": {}
                }, f)
            
            result = runner.invoke(model_command, ["--manifest", manifest_path, "--current"])
            assert result.exit_code == 0
            assert "gpt-4o" in result.output
    
    def test_model_cli_set(self):
        """Test CLI --set flag."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            manifest_path = "conductor.json"
            with open(manifest_path, "w") as f:
                json.dump({"version": "1.0", "metadata": {}, "workflows": {}}, f)
            
            result = runner.invoke(
                model_command,
                ["--manifest", manifest_path, "--set", "claude-3-sonnet"]
            )
            assert result.exit_code == 0
            assert "set to" in result.output.lower()


# ============================================================================
# CONDUCTOR RESUME TESTS
# ============================================================================

class TestResumeCommand:
    """Test conductor resume command."""
    
    def test_resume_get_run_details(self):
        """Test getting blocked run details."""
        recovery = RunRecovery()
        
        with patch.object(recovery.result_store, "get_result") as mock_get:
            mock_result = Mock(
                run_id="RUN-BLOCKED",
                workflow_name="test",
                blocked=True,
                blocked_reason="Human decision required",
                decisions=[],
                payload={"source": "test"},
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:05:00",
            )
            mock_get.return_value = mock_result
            
            details = recovery.get_run_details("RUN-BLOCKED")
            assert details["run_id"] == "RUN-BLOCKED"
            assert details["blocked"] is True
            assert "Human decision" in details["blocked_reason"]
    
    def test_resume_list_blocked_runs(self):
        """Test listing blocked runs."""
        recovery = RunRecovery()
        
        with patch.object(recovery.result_store, "list_runs") as mock_list:
            mock_list.return_value = [
                {"run_id": "RUN-001", "blocked_reason": "Secret detected"},
                {"run_id": "RUN-002", "blocked_reason": "Human gate"},
            ]
            
            runs = recovery.list_blocked_runs()
            assert len(runs) == 2
            assert runs[0]["run_id"] == "RUN-001"
    
    def test_resume_run_success(self):
        """Test successful run resume."""
        recovery = RunRecovery()
        
        with patch.object(recovery.result_store, "get_result") as mock_get, \
             patch.object(recovery.result_store, "save_result") as mock_save:
            
            mock_result = Mock(run_id="RUN-001", blocked=True, payload={})
            mock_get.return_value = mock_result
            
            result = recovery.resume_run("RUN-001", {"updated": True})
            assert result is True
            assert mock_result.blocked is False
            mock_save.assert_called_once()
    
    def test_resume_run_not_blocked(self):
        """Test resume on non-blocked run."""
        recovery = RunRecovery()
        
        with patch.object(recovery.result_store, "get_result") as mock_get:
            mock_result = Mock(run_id="RUN-001", blocked=False)
            mock_get.return_value = mock_result
            
            result = recovery.resume_run("RUN-001")
            assert result is False


# ============================================================================
# CONDUCTOR DIFF TESTS
# ============================================================================

class TestDiffCommand:
    """Test conductor diff command."""
    
    def test_diff_get_proposed_changes(self):
        """Test extracting proposed changes from run."""
        differ = ChangeDiffer()
        
        with patch.object(differ.result_store, "get_result") as mock_get:
            mock_decision = Mock(
                agent="refactor_agent",
                files_modified=[
                    {
                        "path": "src/main.py",
                        "before": "def foo():\n  pass",
                        "after": "def foo():\n  return 42",
                        "type": "modify"
                    }
                ]
            )
            mock_result = Mock(decisions=[mock_decision])
            mock_get.return_value = mock_result
            
            changes = differ.get_proposed_changes("RUN-001")
            assert "src/main.py" in changes["files"]
            assert changes["files"]["src/main.py"]["agent"] == "refactor_agent"
    
    def test_diff_format_unified(self):
        """Test unified diff format."""
        differ = ChangeDiffer()
        
        before = "line 1\nline 2\nline 3\n"
        after = "line 1\nmodified line 2\nline 3\n"
        
        diff = differ.format_unified_diff(before, after, "test.py")
        assert "--- a/test.py" in diff
        assert "+++ b/test.py" in diff
        assert "modified line 2" in diff
    
    def test_diff_format_stat(self):
        """Test stat format."""
        differ = ChangeDiffer()
        
        before = "line 1\nline 2\n"
        after = "line 1\nline 2\nline 3\nline 4\n"
        
        stat = differ.format_stat(before, after)
        assert "0-" in stat
        assert "+2" in stat
    
    def test_diff_cli_output(self):
        """Test CLI diff output."""
        runner = CliRunner()
        
        with patch("conductor_cli.commands.diff_command.ChangeDiffer.get_proposed_changes") as mock_get:
            mock_get.return_value = {
                "files": {
                    "src/main.py": {
                        "agent": "agent_1",
                        "before": "old",
                        "after": "new",
                        "type": "modify"
                    }
                }
            }
            
            result = runner.invoke(diff_command, ["--run-id", "RUN-001", "--format", "list"])
            assert result.exit_code == 0
            assert "src/main.py" in result.output


import asyncio

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
