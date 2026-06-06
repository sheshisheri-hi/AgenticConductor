"""Hook Ordering Guarantee — Deterministic hook execution order (ADR-012).

Ensures hooks always execute in deterministic order regardless of manifest
or policy definitions. Critical for multi-agent reproducibility.

Order: By (stage, priority, hook_id)
- stage: Order within pipeline (string lexicographic)
- priority: 0=highest, 100=lowest
- hook_id: Tie-breaker (alphanumeric)

Example manifest ordering:
  stage_1: {priority: 10}
  stage_2: {priority: 5}   <- executes first (lower priority)
  stage_2: {priority: 10}
  stage_1: {priority: 5}   <- executes last
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class HookOrder:
    """Represents ordered hook execution."""
    stage: str
    priority: int
    hook_id: str
    hook_config: Dict[str, Any]
    
    def sort_key(self) -> Tuple[str, int, str]:
        """Return sort key for deterministic ordering."""
        return (self.stage, self.priority, self.hook_id)
    
    def __lt__(self, other: "HookOrder") -> bool:
        """Compare hooks for sorting."""
        return self.sort_key() < other.sort_key()
    
    def __repr__(self) -> str:
        return f"HookOrder({self.stage}/{self.priority}/{self.hook_id})"


class HookOrderingEngine:
    """Ensures deterministic hook execution order."""
    
    def __init__(self):
        """Initialize engine."""
        self.sorted_hooks: List[HookOrder] = []
    
    def parse_hooks(self, manifest: Dict[str, Any]) -> List[HookOrder]:
        """Parse manifest and return sorted hook list.
        
        Manifest format:
        {
          "hooks": {
            "stage_1": [
              {"id": "hook_a", "priority": 10, "url": "..."},
              {"id": "hook_b", "priority": 5, "url": "..."},
            ]
          }
        }
        
        Returns:
            List of HookOrder sorted by (stage, priority, id)
        """
        self.sorted_hooks = []
        
        hooks_config = manifest.get("hooks", {})
        
        for stage, hook_list in hooks_config.items():
            if not isinstance(hook_list, list):
                # Single hook instead of list
                hook_list = [hook_list]
            
            for hook_config in hook_list:
                hook_id = hook_config.get("id", f"hook_{len(self.sorted_hooks)}")
                priority = hook_config.get("priority", 50)  # 50 = medium priority
                
                hook_order = HookOrder(
                    stage=stage,
                    priority=priority,
                    hook_id=hook_id,
                    hook_config=hook_config,
                )
                self.sorted_hooks.append(hook_order)
        
        # Sort deterministically
        self.sorted_hooks.sort()
        
        logger.info(f"Ordered {len(self.sorted_hooks)} hooks deterministically")
        return self.sorted_hooks
    
    def get_hooks_for_stage(self, stage: str) -> List[HookOrder]:
        """Get all hooks for a specific stage in order."""
        return [h for h in self.sorted_hooks if h.stage == stage]
    
    def get_execution_plan(self) -> str:
        """Get human-readable execution plan."""
        lines = ["Hook Execution Plan (Deterministic Order):", ""]
        
        current_stage = None
        for hook in self.sorted_hooks:
            if hook.stage != current_stage:
                lines.append(f"Stage: {hook.stage}")
                current_stage = hook.stage
            
            lines.append(f"  [{hook.priority:3d}] {hook.hook_id}")
        
        return "\n".join(lines)


class PolicyVisualization:
    """Visualize policies and conflicts in human-readable format."""
    
    @staticmethod
    def format_policy_table(policies: List[Dict[str, Any]]) -> str:
        """Format policies as ASCII table.
        
        Example output:
        ┌─────────────────────────────────────────────┐
        │ Policy Conflict Visualization               │
        ├─────────┬──────────────┬────────┬──────────┤
        │ Field   │ Policy 1     │ Policy │ Result   │
        ├─────────┼──────────────┼────────┼──────────┤
        │ timeout │ 30s          │ 60s    │ 30s ⚠    │  <- CONFLICT
        │ retries │ 3            │ 3      │ 3        │
        │ notify  │ slack        │ pagerduty | CONFLICT ✗
        └─────────┴──────────────┴────────┴──────────┘
        """
        
        # Build table with conflicts highlighted
        lines = [
            "┌─────────────────────────────────────────────────────┐",
            "│ Policy Conflict Analysis                            │",
            "├─────────────┬──────────────┬────────────┬──────────┤",
            "│ Field       │ Value        │ Policy     │ Status   │",
            "├─────────────┼──────────────┼────────────┼──────────┤",
        ]
        
        # Placeholder rows (would be generated from policies)
        lines.append("│ timeout     │ 30s          │ Policy 1   │ OK       │")
        lines.append("│ timeout     │ 60s          │ Policy 2   │ CONFLICT │")
        lines.append("│ retries     │ 3            │ Both       │ OK       │")
        lines.append("└─────────────┴──────────────┴────────────┴──────────┘")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_hook_tree(hooks: List[HookOrder]) -> str:
        """Format hooks as execution tree.
        
        Example:
        Hook Execution Tree
        ├── Stage: analyze
        │   ├── [10] validate_syntax
        │   ├── [ 5] check_security
        │   └── [15] log_metrics
        └── Stage: plan
            └── [50] generate_plan
        """
        
        lines = ["Hook Execution Tree", ""]
        
        stages = {}
        for hook in hooks:
            if hook.stage not in stages:
                stages[hook.stage] = []
            stages[hook.stage].append(hook)
        
        stage_list = sorted(stages.keys())
        for i, stage in enumerate(stage_list):
            is_last_stage = i == len(stage_list) - 1
            stage_prefix = "└──" if is_last_stage else "├──"
            lines.append(f"{stage_prefix} Stage: {stage}")
            
            hooks_in_stage = stages[stage]
            for j, hook in enumerate(hooks_in_stage):
                is_last_hook = j == len(hooks_in_stage) - 1
                hook_prefix = "    " if is_last_stage else "│   "
                hook_symbol = "└──" if is_last_hook else "├──"
                lines.append(f"{hook_prefix}{hook_symbol} [{hook.priority:3d}] {hook.hook_id}")
        
        return "\n".join(lines)


class ConflictResolver:
    """Resolve policy conflicts using predefined rules.
    
    Conflict resolution strategies:
    1. Most restrictive: Use smallest timeout, most security checks
    2. Most permissive: Use largest timeout, fewest checks
    3. Union: Combine all values (lists, sets)
    4. Intersection: Common values only
    5. Manual: Require human review
    """
    
    def __init__(self, strategy: str = "most_restrictive"):
        """Initialize resolver.
        
        Args:
            strategy: "most_restrictive", "most_permissive", "union", "intersection", "manual"
        """
        self.strategy = strategy
    
    def resolve_conflict(
        self,
        field: str,
        values: List[Any],
        policies: List[str],
    ) -> Tuple[Any, str]:
        """Resolve conflicting values.
        
        Returns:
            (resolved_value, explanation)
        """
        if len(set(str(v) for v in values)) == 1:
            # No conflict
            return values[0], "No conflict"
        
        if self.strategy == "most_restrictive":
            # For timeouts: smallest. For retries: smallest. For URLs: first.
            if isinstance(values[0], int):
                resolved = min(values)
            elif isinstance(values[0], str) and any(c.isdigit() for c in values[0]):
                # Parse numbers from strings (e.g., "30s" -> 30)
                resolved = min(values, key=lambda v: int(''.join(filter(str.isdigit, str(v)))))
            else:
                resolved = values[0]
            
            return resolved, f"Chose most restrictive from {policies}"
        
        elif self.strategy == "most_permissive":
            if isinstance(values[0], int):
                resolved = max(values)
            else:
                resolved = values[-1]
            
            return resolved, f"Chose most permissive from {policies}"
        
        elif self.strategy == "union":
            if isinstance(values[0], list):
                resolved = list(set().union(*values))
            elif isinstance(values[0], dict):
                resolved = {}
                for v in values:
                    resolved.update(v)
            else:
                resolved = values  # Keep all
            
            return resolved, f"Union of all policies"
        
        else:  # manual
            return None, f"CONFLICT: Manual review required for {field}: {values}"


if __name__ == "__main__":
    # Example usage
    manifest = {
        "hooks": {
            "stage_1": [
                {"id": "hook_a", "priority": 10, "url": "https://..."},
                {"id": "hook_b", "priority": 5, "url": "https://..."},
            ],
            "stage_2": [
                {"id": "hook_c", "priority": 20, "url": "https://..."},
            ],
        }
    }
    
    engine = HookOrderingEngine()
    hooks = engine.parse_hooks(manifest)
    
    print(engine.get_execution_plan())
    print()
    print(PolicyVisualization.format_hook_tree(hooks))
