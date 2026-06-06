"""Remediation planning agent with schema validation."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any


def bootstrap_conductor_path() -> None:
    """Add conductor-core to sys.path when needed."""
    ai_agents_root = Path(__file__).resolve().parents[4]
    conductor_core_root = ai_agents_root / "conductor-core"
    if conductor_core_root.exists() and str(conductor_core_root) not in sys.path:
        sys.path.insert(0, str(conductor_core_root))


bootstrap_conductor_path()

try:
    from pydantic import BaseModel
    from conductor_core.decorators import AgentOutputValidator, validated_agent
    PYDANTIC_AVAILABLE = True
except Exception:
    PYDANTIC_AVAILABLE = False

    class BaseModel:
        """Tiny fallback model with model_validate compatibility."""

        required_fields: dict[str, type | tuple[type, ...]] = {}

        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

        @classmethod
        def model_validate(cls, data: Any) -> "BaseModel":
            if not isinstance(data, dict):
                raise ValueError("validated payload must be a dict")
            for field, expected_type in cls.required_fields.items():
                if field not in data:
                    raise ValueError(f"missing field: {field}")
                if expected_type is list:
                    if not isinstance(data[field], list):
                        raise ValueError(f"field {field} must be a list")
                elif not isinstance(data[field], expected_type):
                    raise ValueError(f"field {field} must be {expected_type}")
            return cls(**data)

        def model_dump(self) -> dict[str, Any]:
            return dict(self.__dict__)

    def validated_agent(output_schema: type[BaseModel], raise_on_invalid: bool = False):
        """Fallback validated_agent decorator."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                try:
                    return output_schema.model_validate(result)
                except Exception:
                    if raise_on_invalid:
                        raise
                    return result
            return wrapper
        return decorator

    class AgentOutputValidator:
        """Fallback batch validator."""

        def __init__(self) -> None:
            self.validated_count = 0
            self.failed_count = 0
            self.errors: dict[str, str] = {}

        def validate(self, agent_name: str, output: Any, schema: type[BaseModel]) -> tuple[bool, Any]:
            try:
                validated = output if hasattr(output, "model_dump") else schema.model_validate(output)
                self.validated_count += 1
                return True, validated
            except Exception as exc:
                self.failed_count += 1
                self.errors[agent_name] = str(exc)
                return False, None

        def get_summary(self) -> dict[str, Any]:
            return {
                "total_validated": self.validated_count + self.failed_count,
                "successful": self.validated_count,
                "failed": self.failed_count,
                "errors": self.errors,
            }


LOGGER = logging.getLogger(__name__)


class RemediationPlanSchema(BaseModel):
    """Validated output schema for remediation plans."""

    if not PYDANTIC_AVAILABLE:
        required_fields = {
            "finding_id": str,
            "issue_type": str,
            "risk_level": str,
            "fix_steps": list,
            "validation_checks": list,
            "requires_human_review": bool,
            "confidence": float,
        }


def to_plain_dict(model_or_dict: Any) -> dict[str, Any]:
    """Convert validated output to a plain dict."""
    if hasattr(model_or_dict, "model_dump"):
        return model_or_dict.model_dump()
    if isinstance(model_or_dict, dict):
        return model_or_dict
    raise TypeError("plan output must be a dict-like object")


def build_validation_summary(plan_models: list[Any], schema: type[BaseModel]) -> dict[str, Any]:
    """Validate all plan outputs and return a summary."""
    validator = AgentOutputValidator()
    for index, item in enumerate(plan_models, start=1):
        validator.validate(f"remediation_plan_{index}", to_plain_dict(item), schema)
    summary = validator.get_summary()
    if hasattr(summary, "model_dump"):
        return summary.model_dump()
    return summary


@validated_agent(RemediationPlanSchema, raise_on_invalid=False)
async def remediation_plan_agent(context: dict[str, Any], finding: dict[str, Any], analysis: dict[str, Any], **_: Any) -> Any:
    """Generate a step-by-step remediation plan for a finding."""
    if not isinstance(context, dict):
        raise TypeError("context must be a dict")
    if not isinstance(finding, dict) or not isinstance(analysis, dict):
        raise TypeError("finding and analysis must be dicts")

    await asyncio.sleep(0.02)
    issue_type = str(analysis.get("issue_type", "generic_security_issue"))
    fix_steps = [
        f"Open {finding.get('file_path', 'unknown file')} and isolate the vulnerable code path.",
        f"Apply the recommended package or code fix for {issue_type}.",
        "Add or update automated tests that reproduce the vulnerable behavior.",
        "Run dependency and regression checks before merging the patch.",
    ]
    if issue_type == "unsafe_deserialization":
        fix_steps.insert(1, "Replace yaml.load with yaml.safe_load and reject object constructors.")
    if issue_type == "sensitive_data_exposure":
        fix_steps.insert(1, "Remove secrets from responses, logs, and telemetry payloads.")

    plan = {
        "finding_id": str(finding.get("id", "unknown")),
        "issue_type": issue_type,
        "risk_level": str(finding.get("severity", "medium")),
        "fix_steps": fix_steps,
        "validation_checks": [
            "Schema validation via @validated_agent",
            "Unit or integration tests for the affected endpoint",
            "Manual reviewer sign-off because human_gate=true",
        ],
        "requires_human_review": True,
        "confidence": 0.91,
    }
    LOGGER.info("Generated remediation plan for %s", plan["finding_id"])
    return plan
