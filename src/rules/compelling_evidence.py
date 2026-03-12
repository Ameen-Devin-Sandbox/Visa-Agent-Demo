"""Compelling evidence evaluation logic.

Implements Visa Core Rules Section 11.5.2 (Use of Compelling Evidence) for
pre-arbitration processing.
"""

from dataclasses import dataclass
from datetime import datetime

from src.models.dispute import DisputeCase, DisputeEvidence, RuleEvaluationResult
from src.models.enums import DisputeCondition


@dataclass
class CompellingEvidenceResult:
    """Result of compelling evidence evaluation."""

    is_compelling: bool
    evidence_type: str
    description: str
    rule_section: str


# Compelling evidence types per dispute condition
# Per Section 11.5.2: Compelling Evidence is evidence that the Acquirer may provide
# in a pre-Arbitration attempt to support that the Transaction is valid.
COMPELLING_EVIDENCE_TYPES: dict[DisputeCondition, list[dict[str, str]]] = {
    DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
        {
            "type": "previous_undisputed_transactions",
            "description": (
                "At least two prior undisputed transactions with matching key data elements "
                "(IP address, device ID/fingerprint, or shipping address) linking the "
                "cardholder to the disputed transaction"
            ),
            "rule_section": "11.5.2",
        },
        {
            "type": "delivery_confirmation",
            "description": (
                "Evidence of delivery to the cardholder's address that matches "
                "the AVS-verified address (AVS result code Y)"
            ),
            "rule_section": "11.5.2",
        },
        {
            "type": "cardholder_identity_verification",
            "description": (
                "Evidence that the cardholder's identity was verified through "
                "additional authentication (e.g., biometric, 3-D Secure)"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.EMV_COUNTERFEIT_FRAUD: [
        {
            "type": "chip_reading_evidence",
            "description": (
                "Evidence that the transaction was processed at a chip-reading device "
                "and full chip data was transmitted"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.MERCHANDISE_NOT_RECEIVED: [
        {
            "type": "delivery_proof",
            "description": (
                "Proof of delivery signed by the cardholder or authorized person, "
                "including tracking information and delivery confirmation"
            ),
            "rule_section": "11.5.2",
        },
        {
            "type": "digital_delivery_proof",
            "description": (
                "For digital goods: evidence of download/access by the cardholder, "
                "including IP address, device fingerprint, or usage logs"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.NOT_AS_DESCRIBED: [
        {
            "type": "product_description_match",
            "description": (
                "Evidence that the merchandise/services matched the original description "
                "provided to the cardholder at the time of purchase"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.CANCELLED_RECURRING: [
        {
            "type": "no_cancellation_record",
            "description": (
                "Evidence that no cancellation request was received before the "
                "transaction date, or that the cancellation policy was not followed"
            ),
            "rule_section": "11.5.2",
        },
        {
            "type": "cancellation_terms",
            "description": (
                "Evidence of the agreed-upon cancellation terms that the cardholder "
                "accepted at the time of the original transaction"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.CREDIT_NOT_PROCESSED: [
        {
            "type": "credit_processed_evidence",
            "description": (
                "Evidence that the credit was already processed, including "
                "transaction identifiers and processing dates"
            ),
            "rule_section": "11.5.2",
        },
    ],
    DisputeCondition.CANCELLED_MERCHANDISE: [
        {
            "type": "no_return_evidence",
            "description": (
                "Evidence that the merchandise was not returned, or services "
                "were fully provided before cancellation"
            ),
            "rule_section": "11.5.2",
        },
        {
            "type": "cancellation_policy",
            "description": (
                "Evidence that the cancellation/return policy was disclosed to "
                "the cardholder and not followed"
            ),
            "rule_section": "11.5.2",
        },
    ],
}


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
                description=f"No compelling evidence types defined for condition {case.condition.value}",
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
                    description=f"Evidence type '{evidence.evidence_type}' does not match any compelling evidence criteria",
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

    type_keywords: dict[str, list[str]] = {
        "previous_undisputed_transactions": [
            "prior",
            "previous",
            "undisputed",
            "ip address",
            "device",
        ],
        "delivery_confirmation": ["delivery", "delivered", "shipping", "avs", "address"],
        "cardholder_identity_verification": [
            "identity",
            "biometric",
            "3ds",
            "3-d secure",
            "authentication",
        ],
        "chip_reading_evidence": ["chip", "emv", "full chip data"],
        "delivery_proof": ["delivery", "tracking", "signed", "proof of delivery"],
        "digital_delivery_proof": ["download", "digital", "access log", "usage"],
        "product_description_match": ["description", "product", "match", "as described"],
        "no_cancellation_record": ["cancellation", "no record", "not cancelled"],
        "cancellation_terms": ["cancellation terms", "policy", "terms and conditions"],
        "credit_processed_evidence": ["credit", "processed", "refund", "transaction id"],
        "no_return_evidence": ["return", "not returned", "merchandise"],
        "cancellation_policy": ["cancellation policy", "return policy", "disclosed"],
    }

    keywords = type_keywords.get(evidence_type, [])
    return any(keyword in type_lower or keyword in desc_lower for keyword in keywords)


def convert_to_rule_evaluation(result: CompellingEvidenceResult) -> RuleEvaluationResult:
    """Convert a compelling evidence result to a rule evaluation for recording."""
    return RuleEvaluationResult(
        rule_id=f"compelling_evidence_{result.evidence_type}",
        rule_section=result.rule_section,
        rule_description=result.description,
        is_satisfied=result.is_compelling,
        details=result.description,
        evaluated_at=datetime.utcnow(),
    )
