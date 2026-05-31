"""WorkflowGraph — loads and validates workflow YAML definitions.

The consumer declares their pipeline in workflow.yaml. The framework
loads it, validates the schema, and the orchestrator uses it to drive
stage transitions.

Minimal workflow.yaml schema:
  workflow:
    name: security_remediation
    mode: plan          # plan | execute
    stop_before: []     # stage names where mode=plan halts

  stages:
    - name: triage
      agent: triage
      on_proceed: plan
      on_block: escalate_human
      on_escalate: escalate_human

  human_gates:
    - stage: plan
      notify_channel: "#security-triage"

  parallel_groups:
    - trigger_stage: review_gate
      agents: [security_gatekeeper, reviewer]
      merge_strategy: all_must_pass
      next_stage_on_pass: document
      next_stage_on_block: terminal
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from conductor_core.exceptions import WorkflowGraphError


class StageConfig:
    """Config for a single workflow stage."""

    def __init__(self, data: dict) -> None:
        self.name: str = data["name"]
        self.agent: str = data.get("agent", "")
        self.on_proceed: str = data.get("on_proceed", "")
        self.on_block: str = data.get("on_block", "terminal")
        self.on_escalate: str = data.get("on_escalate", "escalate_human")
        self.on_plan_only: str = data.get("on_plan_only", "terminal")
        self.parallel_group: list[str] = data.get("parallel_group", [])
        self.stop_before: bool = data.get("stop_before", False)
        # Optional model override for this stage — takes priority over agent's
        # class-level MODEL_OVERRIDE and global settings.llm_model.
        # Example in YAML:  model: o1-preview
        self.model: str | None = data.get("model")
        self.raw: dict = data


class ParallelGroup:
    """Configuration for a parallel stage group."""

    def __init__(self, data: dict) -> None:
        self.trigger_stage: str = data["trigger_stage"]
        self.agents: list[str] = data.get("agents", [])
        self.merge_strategy: str = data.get("merge_strategy", "all_must_pass")
        self.next_stage_on_pass: str = data.get("next_stage_on_pass", "")
        self.next_stage_on_block: str = data.get("next_stage_on_block", "terminal")


class WorkflowGraph:
    """Parsed and validated workflow YAML.

    Loaded once at startup. Passed to WorkflowOrchestrator.
    """

    def __init__(
        self,
        name: str,
        mode: str,
        stages: list[StageConfig],
        stop_before: list[str],
        human_gates: list[dict],
        filters: list[dict],
        routes: list[dict],
        parallel_groups: list[ParallelGroup] | None = None,
    ) -> None:
        self.name = name
        self.mode = mode
        self.stages = stages
        self.stop_before = stop_before
        self.human_gates = human_gates
        self.filters = filters
        self.routes = routes
        self.parallel_groups: list[ParallelGroup] = parallel_groups or []
        self._stage_map: dict[str, StageConfig] = {s.name: s for s in stages}
        self._parallel_group_map: dict[str, ParallelGroup] = {
            pg.trigger_stage: pg for pg in self.parallel_groups
        }

    def get_stage(self, name: str) -> StageConfig | None:
        return self._stage_map.get(name)

    def get_parallel_group(self, stage: str) -> ParallelGroup | None:
        """Return the ParallelGroup for the given trigger stage, or None."""
        return self._parallel_group_map.get(stage)

    def first_stage(self) -> StageConfig:
        if not self.stages:
            raise WorkflowGraphError("Workflow has no stages defined")
        return self.stages[0]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "WorkflowGraph":
        """Load and validate a workflow YAML file.

        Args:
            path: Path to the workflow YAML file.

        Returns:
            Parsed WorkflowGraph.

        Raises:
            WorkflowGraphError: If file not found or schema invalid.
        """
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise WorkflowGraphError(f"Workflow YAML not found: {yaml_path}")

        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise WorkflowGraphError(f"Invalid YAML in {yaml_path}: {e}") from e

        return cls.from_dict(raw, source=str(yaml_path))

    @classmethod
    def from_dict(cls, raw: dict, source: str = "<dict>") -> "WorkflowGraph":
        """Parse a workflow definition from a dict (for testing).

        Args:
            raw: Dict matching the workflow YAML schema.
            source: Source identifier for error messages.

        Returns:
            Parsed WorkflowGraph.
        """
        cls._validate(raw, source)

        wf = raw.get("workflow", {})
        name = wf.get("name", "unnamed")
        mode = wf.get("mode", "plan")
        stop_before = wf.get("stop_before", [])

        stages = [StageConfig(s) for s in raw.get("stages", [])]
        human_gates = raw.get("human_gates", [])
        filters = raw.get("filters", [])
        routes = raw.get("routes", [])
        parallel_groups = [ParallelGroup(pg) for pg in raw.get("parallel_groups", [])]

        return cls(
            name=name,
            mode=mode,
            stages=stages,
            stop_before=stop_before,
            human_gates=human_gates,
            filters=filters,
            routes=routes,
            parallel_groups=parallel_groups,
        )

    @staticmethod
    def _validate(raw: Any, source: str) -> None:
        if not isinstance(raw, dict):
            raise WorkflowGraphError(f"{source}: top-level must be a YAML mapping")
        if "stages" not in raw:
            raise WorkflowGraphError(f"{source}: missing required 'stages' key")
        # Build set of parallel trigger stages — they don't need an agent
        parallel_triggers = {
            pg.get("trigger_stage")
            for pg in raw.get("parallel_groups", [])
            if isinstance(pg, dict)
        }
        for i, stage in enumerate(raw.get("stages", [])):
            if "name" not in stage:
                raise WorkflowGraphError(f"{source}: stage[{i}] missing 'name'")
            if "agent" not in stage and stage.get("name") not in parallel_triggers:
                raise WorkflowGraphError(f"{source}: stage[{i}] missing 'agent'")

