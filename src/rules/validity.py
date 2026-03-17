# THIS FILE IS AUTO-GENERATED from rules/generated/validity.yaml
# DO NOT EDIT MANUALLY. Run `python scripts/generate_rules.py` to regenerate.
# Source: Visa Core Rules V1.1 - 18 October 2025
"""Dispute validity checking logic.

Data-driven validity checker loaded from rules/generated/validity.yaml.
Each dispute condition has specific circumstances that make a dispute invalid.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import DisputeCondition


@dataclass
class ValidityCheckResult:
    """Result of a dispute validity check."""

    is_valid: bool
    reason: str
    rule_section: str
    condition_checked: str


# Load validity rules from YAML at import time
_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "rules" / "generated" / "validity.yaml"
with open(_YAML_PATH, encoding="utf-8") as _f:
    _VALIDITY_DATA: dict[str, Any] = yaml.safe_load(_f)
_CONDITIONS: dict[str, Any] = _VALIDITY_DATA.get("conditions", {})


def _resolve_field(obj: Any, field_path: str) -> Any:
    """Traverse dotted paths on Pydantic models or dicts."""
    parts = field_path.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        current = current.get(part) if isinstance(current, dict) else getattr(current, part, None)
    return current


def _evaluate_rule(
    case: DisputeCase, rule: dict[str, Any], rule_section: str
) -> ValidityCheckResult | None:
    """Evaluate a single validity rule against a case.

    Returns a result if the rule triggers (i.e., the dispute is invalid).
    """
    field_path = rule["field"]
    reason = rule["reason"]
    value = _resolve_field(case, field_path)

    # Handle different comparison operators
    if "equals" in rule:
        expected = rule["equals"]

        # Handle enum values - compare by .value if available
        actual = value.value if hasattr(value, "value") else value

        if actual != expected:
            return None

        # Check additional constraints if present
        if "additional_field" in rule:
            add_value = _resolve_field(case, rule["additional_field"])
            add_actual = add_value.value if hasattr(add_value, "value") else add_value
            if "additional_equals_any" in rule and add_actual not in rule["additional_equals_any"]:
                return None
            if "additional_not_equals" in rule and add_actual == rule["additional_not_equals"]:
                return None

    elif "not_equals" in rule:
        expected = rule["not_equals"]
        actual = value.value if hasattr(value, "value") else value
        if actual == expected:
            return None

    elif "starts_with" in rule:
        if value is None or not str(value).startswith(rule["starts_with"]):
            return None

    elif "is_truthy" in rule:
        if not value:
            return None

    elif "is_empty" in rule:
        if value:
            return None

    else:
        return None

    # Build a condition_checked identifier from the field path
    condition_checked = field_path.split(".")[-1]

    return ValidityCheckResult(
        is_valid=False,
        reason=reason,
        rule_section=rule_section,
        condition_checked=condition_checked,
    )


def check_validity(
    case: DisputeCase, condition: DisputeCondition
) -> list[ValidityCheckResult]:
    """Check validity of a dispute using data-driven rules from YAML.

    Args:
        case: The dispute case to evaluate.
        condition: The dispute condition to check against.

    Returns:
        List of validity check results.
    """
    cond_data = _CONDITIONS.get(condition.value)
    if cond_data is None:
        return [
            ValidityCheckResult(
                is_valid=True,
                reason=f"No specific validity checker for {condition.value}; default valid",
                rule_section="11.6",
                condition_checked="default_pass",
            )
        ]

    rule_section = cond_data["rule_section"]
    invalid_rules = cond_data.get("invalid_when", [])
    results: list[ValidityCheckResult] = []

    for rule in invalid_rules:
        result = _evaluate_rule(case, rule, rule_section)
        if result is not None:
            results.append(result)

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason=f"No invalid conditions found for {condition.value}",
                rule_section=rule_section,
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_dispute_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Run all applicable validity checks for a dispute case.

    Returns a list of validity check results. If any result has is_valid=False,
    the dispute is considered invalid under that condition.
    """
    if case.condition is None:
        return [
            ValidityCheckResult(
                is_valid=False,
                reason="No dispute condition assigned",
                rule_section="11.6",
                condition_checked="condition_assignment",
            )
        ]

    return check_validity(case, case.condition)


def convert_to_rule_evaluation(result: ValidityCheckResult) -> RuleEvaluationResult:
    """Convert a validity check result to a rule evaluation result for recording."""
    return RuleEvaluationResult(
        rule_id=f"validity_{result.condition_checked}",
        rule_section=result.rule_section,
        rule_description=result.reason,
        is_satisfied=result.is_valid,
        details=result.reason,
        evaluated_at=datetime.utcnow(),
    )
