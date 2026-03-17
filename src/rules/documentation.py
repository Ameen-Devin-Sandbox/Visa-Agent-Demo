# THIS FILE IS AUTO-GENERATED from rules/generated/documentation.yaml
# DO NOT EDIT MANUALLY. Run `python scripts/generate_rules.py` to regenerate.
# Source: Visa Core Rules V1.1 - 18 October 2025
"""Documentation and certification requirement validators.

Loaded from rules/generated/documentation.yaml. Encodes the required
documentation/certification for each dispute condition as specified in
Visa Core Rules Section 11.7-11.10.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.models.dispute import DisputeCase
from src.models.enums import DisputeCondition, FraudTypeCode


@dataclass
class DocumentationRequirement:
    """A required document or certification for a dispute condition."""

    requirement_id: str
    description: str
    is_mandatory: bool
    rule_section: str
    condition: str


@dataclass
class DocumentationCheckResult:
    """Result of checking documentation requirements."""

    is_complete: bool
    met_requirements: list[str]
    missing_requirements: list[str]
    details: str


# Load documentation rules from YAML at import time
_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "rules"
    / "generated"
    / "documentation.yaml"
)
with open(_YAML_PATH, encoding="utf-8") as _f:
    _DOC_DATA: dict[str, Any] = yaml.safe_load(_f)


def _build_requirements() -> dict[DisputeCondition, list[DocumentationRequirement]]:
    """Build the DOCUMENTATION_REQUIREMENTS dict from YAML data."""
    result: dict[DisputeCondition, list[DocumentationRequirement]] = {}
    for cond_code, reqs in _DOC_DATA.get("requirements", {}).items():
        try:
            condition = DisputeCondition(cond_code)
        except ValueError:
            continue
        result[condition] = [
            DocumentationRequirement(
                requirement_id=r["requirement_id"],
                description=r["description"],
                is_mandatory=r["is_mandatory"],
                rule_section=r["rule_section"],
                condition=cond_code,
            )
            for r in reqs
        ]
    return result


DOCUMENTATION_REQUIREMENTS = _build_requirements()


def _build_letter_requirements() -> tuple[list[str], list[str]]:
    """Build cardholder letter requirements from YAML data."""
    letter_reqs = _DOC_DATA.get("cardholder_letter_requirements", {})
    cat_10: list[str] = letter_reqs.get("category_10", [])
    cat_13: list[str] = letter_reqs.get("category_13", [])
    return cat_10, cat_13


CATEGORY_10_LETTER_REQUIREMENTS, CATEGORY_13_LETTER_REQUIREMENTS = (
    _build_letter_requirements()
)


def _build_fraud_code_requirements() -> dict[DisputeCondition, list[FraudTypeCode]]:
    """Build fraud type code requirements from YAML data."""
    result: dict[DisputeCondition, list[FraudTypeCode]] = {}
    for cond_code, req_data in _DOC_DATA.get(
        "fraud_type_code_requirements", {}
    ).items():
        try:
            condition = DisputeCondition(cond_code)
        except ValueError:
            continue
        result[condition] = [FraudTypeCode(c) for c in req_data["allowed_codes"]]
    return result


_FRAUD_CODE_REQUIREMENTS = _build_fraud_code_requirements()


def check_fraud_type_code_requirement(case: DisputeCase) -> DocumentationCheckResult:
    """Check that the correct fraud type code was reported for Category 10 conditions.

    Per Section 11.7.2.2: Before initiating a Dispute, an Issuer must report
    the Fraud Activity to Visa using the appropriate fraud type code.
    """
    if case.condition is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["dispute_condition_not_assigned"],
            details="Cannot check fraud type code: no dispute condition assigned",
        )

    if case.condition not in _FRAUD_CODE_REQUIREMENTS:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=["no_fraud_code_required"],
            missing_requirements=[],
            details="No specific fraud type code required for this condition",
        )

    allowed = _FRAUD_CODE_REQUIREMENTS[case.condition]
    if case.fraud_type_code is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["fraud_type_code"],
            details=f"Fraud type code not reported. Required: {[c.value for c in allowed]}",
        )

    if case.fraud_type_code in allowed:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=["fraud_type_code"],
            missing_requirements=[],
            details=f"Correct fraud type code reported: {case.fraud_type_code.value}",
        )

    return DocumentationCheckResult(
        is_complete=False,
        met_requirements=[],
        missing_requirements=["fraud_type_code_mismatch"],
        details=(
            f"Incorrect fraud type code: {case.fraud_type_code.value}. "
            f"Required: {[c.value for c in allowed]}"
        ),
    )


def check_documentation_requirements(case: DisputeCase) -> DocumentationCheckResult:
    """Check all documentation requirements for a dispute case.

    Validates that all mandatory documentation and certifications
    have been provided for the assigned dispute condition.
    """
    if case.condition is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["condition_not_assigned"],
            details="Cannot check documentation: no dispute condition assigned",
        )

    requirements = DOCUMENTATION_REQUIREMENTS.get(case.condition, [])
    if not requirements:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=[],
            missing_requirements=[],
            details=f"No specific documentation requirements for {case.condition.value}",
        )

    met: list[str] = []
    missing: list[str] = []

    # Check if issuer certification is provided (covers most certification requirements)
    has_certification = case.issuer_certification is not None
    has_cardholder_letter = case.cardholder.signed_letter_provided
    has_evidence = len(case.evidence) > 0

    for req in requirements:
        if not req.is_mandatory:
            continue

        # Simple heuristic: check if we have the general type of documentation
        if "certification" in req.description.lower() or "certif" in req.requirement_id:
            if has_certification or has_cardholder_letter:
                met.append(req.requirement_id)
            else:
                missing.append(req.requirement_id)
        elif (
            "fraud" in req.requirement_id.lower()
            and "report" in req.requirement_id.lower()
        ):
            if case.fraud_type_code is not None:
                met.append(req.requirement_id)
            else:
                missing.append(req.requirement_id)
        elif has_evidence:
            met.append(req.requirement_id)
        else:
            missing.append(req.requirement_id)

    is_complete = len(missing) == 0

    return DocumentationCheckResult(
        is_complete=is_complete,
        met_requirements=met,
        missing_requirements=missing,
        details=(
            f"Documentation check: {len(met)} met, {len(missing)} missing"
            if missing
            else "All documentation requirements met"
        ),
    )
