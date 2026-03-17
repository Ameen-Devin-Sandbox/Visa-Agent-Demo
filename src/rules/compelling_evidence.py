# THIS FILE IS AUTO-GENERATED from rules/generated/compelling_evidence.yaml
# DO NOT EDIT MANUALLY. Run `python scripts/generate_rules.py` to regenerate.
# Source: Visa Core Rules V1.1 - 18 October 2025
"""Compelling evidence evaluation logic.

Loaded from rules/generated/compelling_evidence.yaml.
Implements Visa Core Rules Section 11.5.2 (Use of Compelling Evidence) for
pre-arbitration processing.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.models.dispute import DisputeCase, DisputeEvidence, RuleEvaluationResult
from src.models.enums import DisputeCondition


@dataclass
class CompellingEvidenceResult:
    """Result of compelling evidence evaluation."""

    is_compelling: bool
    evidence_type: str
    description: str
    rule_section: str


# Load compelling evidence rules from YAML at import time
_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "rules"
    / "generated"
    / "compelling_evidence.yaml"
)
with open(_YAML_PATH, encoding="utf-8") as _f:
    _CE_DATA: dict[str, Any] = yaml.safe_load(_f)


def _build_evidence_types() -> dict[DisputeCondition, list[dict[str, str]]]:
    """Build COMPELLING_EVIDENCE_TYPES from YAML data."""
    result: dict[DisputeCondition, list[dict[str, str]]] = {}
    for cond_code, evidence_list in _CE_DATA.get("evidence_types", {}).items():
        try:
            condition = DisputeCondition(cond_code)
        except ValueError:
            continue
        result[condition] = evidence_list
    return result


def _build_keyword_mappings() -> dict[str, list[str]]:
    """Build keyword mappings from YAML data."""
    return _CE_DATA.get("keyword_mappings", {})


# Compelling evidence types per dispute condition
COMPELLING_EVIDENCE_TYPES = _build_evidence_types()
_TYPE_KEYWORDS = _build_keyword_mappings()


def evaluate_compelling_evidence(
    case: DisputeCase,
    acquirer_evidence: list[DisputeEvidence],
) -> list[CompellingEvidenceResult]:
    """Evaluate whether acquirer-provided evidence qualifies as compelling.

    Per Section 11.5.2: If the Acquirer provides Compelling Evidence in a
    pre-Arbitration attempt, the Issuer must evaluate it and either accept
    financial responsibility or certify why the cardholder continues to
    dispute the transaction.

    Args:
        case: The dispute case being processed.
        acquirer_evidence: Evidence provided by the acquirer.

    Returns:
        List of evaluation results for each piece of evidence.
    """
    results: list[CompellingEvidenceResult] = []

    if case.condition is None:
        results.append(
            CompellingEvidenceResult(
                is_compelling=False,
                evidence_type="none",
                description="No dispute condition assigned; cannot evaluate compelling evidence",
                rule_section="11.5.2",
            )
        )
        return results

    allowed_types = COMPELLING_EVIDENCE_TYPES.get(case.condition, [])
    if not allowed_types:
        results.append(
            CompellingEvidenceResult(
                is_compelling=False,
                evidence_type="not_applicable",
                description=(
                    f"No compelling evidence types defined for condition "
                    f"{case.condition.value}"
                ),
                rule_section="11.5.2",
            )
        )
        return results

    for evidence in acquirer_evidence:
        if not evidence.is_compelling_evidence:
            continue

        # Check if the evidence type matches any allowed compelling evidence type
        matched = False
        for allowed in allowed_types:
            if _evidence_matches_type(evidence, allowed["type"]):
                results.append(
                    CompellingEvidenceResult(
                        is_compelling=True,
                        evidence_type=allowed["type"],
                        description=f"Evidence matches: {allowed['description']}",
                        rule_section=allowed["rule_section"],
                    )
                )
                matched = True
                break

        if not matched:
            results.append(
                CompellingEvidenceResult(
                    is_compelling=False,
                    evidence_type=evidence.evidence_type,
                    description=(
                        f"Evidence type '{evidence.evidence_type}' does not match "
                        f"any compelling evidence criteria"
                    ),
                    rule_section="11.5.2",
                )
            )

    if not results:
        results.append(
            CompellingEvidenceResult(
                is_compelling=False,
                evidence_type="none_provided",
                description="No compelling evidence was provided by the acquirer",
                rule_section="11.5.2",
            )
        )

    return results


def _evidence_matches_type(evidence: DisputeEvidence, evidence_type: str) -> bool:
    """Check if a piece of evidence matches a compelling evidence type.

    This performs a semantic matching based on the evidence type and description.
    """
    type_lower = evidence.evidence_type.lower()
    desc_lower = evidence.description.lower()

    keywords = _TYPE_KEYWORDS.get(evidence_type, [])
    return any(
        keyword in type_lower or keyword in desc_lower for keyword in keywords
    )


def convert_to_rule_evaluation(
    result: CompellingEvidenceResult,
) -> RuleEvaluationResult:
    """Convert a compelling evidence result to a rule evaluation for recording."""
    return RuleEvaluationResult(
        rule_id=f"compelling_evidence_{result.evidence_type}",
        rule_section=result.rule_section,
        rule_description=result.description,
        is_satisfied=result.is_compelling,
        details=result.description,
        evaluated_at=datetime.utcnow(),
    )
