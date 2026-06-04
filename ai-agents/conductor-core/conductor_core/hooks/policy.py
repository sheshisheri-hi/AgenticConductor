"""PolicyResolver: Merges conductor.json from multiple sources (ADR-012).

Implements GitHub's conflict resolution rules:
- Least restrictive wins for most features (default behavior)
- Most restrictive wins for sensitive operations (configurable per field)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PolicyMergeRule:
    """Rule for merging policy fields."""
    field_name: str
    merge_strategy: str  # "least_restrictive", "most_restrictive", "merge_list", "first_wins"
    locked: bool = False  # If True, field cannot be overridden


class PolicyResolver:
    """Resolves conflicts when multiple conductor.json policies are loaded.
    
    Loading order (highest precedence first):
    1. Command-line arguments
    2. Environment variables
    3. User-level config (~/.conductor/config.json)
    4. Project-level config (conductor.json)
    5. Integration defaults
    """
    
    # Fields that use most-restrictive merge (security-sensitive)
    MOST_RESTRICTIVE_FIELDS = {
        "strict",  # If any org requires strict mode, all must be strict
        "disable_dangerous_integrations",
    }
    
    # Fields that are merged (lists combined)
    MERGE_LIST_FIELDS = {
        "integrations",
        "disabled_agents",
        "disabled_features",
    }
    
    # Fields that use first-wins (don't override)
    FIRST_WINS_FIELDS = {
        "name",
        "version",
        "author",
    }
    
    def __init__(self):
        self.policies: List[Dict[str, Any]] = []
        self.rules: Dict[str, PolicyMergeRule] = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default merge rules."""
        # Most restrictive
        for field in self.MOST_RESTRICTIVE_FIELDS:
            self.rules[field] = PolicyMergeRule(field, "most_restrictive")
        
        # Merge lists
        for field in self.MERGE_LIST_FIELDS:
            self.rules[field] = PolicyMergeRule(field, "merge_list")
        
        # First wins
        for field in self.FIRST_WINS_FIELDS:
            self.rules[field] = PolicyMergeRule(field, "first_wins")
        
        # Default: least restrictive
        # (covered by default case in _merge_values)
    
    def register_rule(self, rule: PolicyMergeRule) -> None:
        """Register a custom merge rule.
        
        Args:
            rule: PolicyMergeRule to register
        """
        self.rules[rule.field_name] = rule
        logger.debug(f"Registered merge rule for {rule.field_name}: {rule.merge_strategy}")
    
    def load_policy(self, path: Path, source: str = "unknown") -> bool:
        """Load a policy file and register it.
        
        Args:
            path: Path to conductor.json
            source: Description of source (for logging)
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(path) as f:
                policy = json.load(f)
            
            self.policies.append({
                "source": source,
                "path": str(path),
                "data": policy
            })
            
            logger.info(f"Loaded policy from {source}: {path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load policy from {source}: {e}")
            return False
    
    def resolve(self) -> Dict[str, Any]:
        """Resolve all loaded policies into single config.
        
        Returns:
            Merged policy dict
        """
        if not self.policies:
            logger.warning("No policies loaded")
            return {}
        
        # Start with first policy as base
        result = {}
        
        # Apply each policy in order
        for policy_entry in self.policies:
            policy = policy_entry["data"]
            source = policy_entry["source"]
            
            logger.debug(f"Applying policy from {source}")
            
            for field, value in policy.items():
                rule = self.rules.get(field)
                strategy = rule.merge_strategy if rule else "least_restrictive"
                
                if field not in result:
                    result[field] = value
                    logger.debug(f"  {field} = {value} (new)")
                else:
                    merged = self._merge_values(field, result[field], value, strategy)
                    if merged != result[field]:
                        logger.debug(f"  {field} = {merged} (merged from {result[field]})")
                    result[field] = merged
        
        return result
    
    def _merge_values(self,
                     field: str,
                     current: Any,
                     new: Any,
                     strategy: str) -> Any:
        """Merge two values according to strategy.
        
        Args:
            field: Field name
            current: Current value
            new: New value to merge
            strategy: Merge strategy
            
        Returns:
            Merged value
        """
        if strategy == "most_restrictive":
            # For booleans: True is more restrictive
            if isinstance(current, bool) and isinstance(new, bool):
                return current or new
            # For strings: prefer the longer/more specific one
            if isinstance(current, str) and isinstance(new, str):
                return new if len(new) > len(current) else current
            # Default: use new
            return new
        
        elif strategy == "merge_list":
            # Combine lists, remove duplicates
            if not isinstance(current, list):
                current = [current] if current else []
            if not isinstance(new, list):
                new = [new] if new else []
            return list(set(current + new))
        
        elif strategy == "first_wins":
            # Keep current, don't override
            return current
        
        else:  # least_restrictive (default)
            # For booleans: False is less restrictive
            if isinstance(current, bool) and isinstance(new, bool):
                return current and new
            # For numbers: smaller value is less restrictive
            if isinstance(current, (int, float)) and isinstance(new, (int, float)):
                return min(current, new)
            # For strings: prefer shorter
            if isinstance(current, str) and isinstance(new, str):
                return new if len(new) < len(current) else current
            # Default: use new
            return new
    
    def check_conflicts(self) -> Dict[str, List[Any]]:
        """Detect conflicts across policies.
        
        Returns:
            Dict of field_name -> [conflicting_values]
        """
        conflicts = {}
        
        for field in set(k for p in self.policies for k in p["data"].keys()):
            values = [p["data"].get(field) for p in self.policies if field in p["data"]]
            
            if len(set(str(v) for v in values)) > 1:
                conflicts[field] = values
                logger.warning(f"Conflict detected in field '{field}': {values}")
        
        return conflicts
    
    def get_sources(self) -> List[str]:
        """Get list of loaded policy sources."""
        return [p["source"] for p in self.policies]


# Example usage and common merge rules
def create_standard_rules() -> List[PolicyMergeRule]:
    """Create standard merge rules for common scenarios."""
    return [
        # Security: most restrictive
        PolicyMergeRule("strict", "most_restrictive"),
        PolicyMergeRule("confidence_threshold", "most_restrictive"),  # Higher is stricter
        
        # Features: merge lists
        PolicyMergeRule("integrations", "merge_list"),
        PolicyMergeRule("disabled_agents", "merge_list"),
        
        # Metadata: first wins
        PolicyMergeRule("name", "first_wins"),
        PolicyMergeRule("version", "first_wins"),
        PolicyMergeRule("author", "first_wins"),
    ]
