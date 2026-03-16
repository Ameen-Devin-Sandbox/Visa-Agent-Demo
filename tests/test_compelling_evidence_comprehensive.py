"""Comprehensive tests for compelling evidence evaluation.

Tests per Section 11.5.2 of the Visa Core Rules.
"""

from datetime import date

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    DisputeCondition,
    Region,
    TransactionEnvironment,
)
from src.rules.compelling_evidence import (
    COMPELLING_EVIDENCE_TYPES,
    _evidence_matches_type,
    convert_to_rule_evaluation,
    evaluate_compelling_evidence,
)


def _make_case(condition: DisputeCondition | None = None) -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-CE-001",
            transaction_date=date(2026, 2, 15),
            processing_date=date(2026, 2, 16),
            amount=500.0,
            currency="USD",
            merchant_name="TestMerchant",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Test User",
            partial_payment_credential="****1234",
        ),
        condition=condition,
    )


def _compelling_evidence(
    description: str,
    evidence_type: str = "compelling",
) -> DisputeEvidence:
    return DisputeEvidence(
        description=description,
        evidence_type=evidence_type,
        provided_by="acquirer",
        is_compelling_evidence=True,
    )


def _regular_evidence(description: str) -> DisputeEvidence:
    return DisputeEvidence(
        description=description,
        evidence_type="general",
        provided_by="acquirer",
        is_compelling_evidence=False,
    )


# ============================================================================
# Compelling evidence types registry
# ============================================================================


class TestCompellingEvidenceRegistry:
    """Test the compelling evidence types mapping."""

    def test_card_absent_has_types(self) -> None:
        assert DisputeCondition.OTHER_FRAUD_CARD_ABSENT in COMPELLING_EVIDENCE_TYPES
        types = COMPELLING_EVIDENCE_TYPES[DisputeCondition.OTHER_FRAUD_CARD_ABSENT]
        assert len(types) >= 3

    def test_emv_counterfeit_has_types(self) -> None:
        assert DisputeCondition.EMV_COUNTERFEIT_FRAUD in COMPELLING_EVIDENCE_TYPES

    def test_merchandise_not_received_has_types(self) -> None:
        assert DisputeCondition.MERCHANDISE_NOT_RECEIVED in COMPELLING_EVIDENCE_TYPES
        types = COMPELLING_EVIDENCE_TYPES[DisputeCondition.MERCHANDISE_NOT_RECEIVED]
        type_names = [t["type"] for t in types]
        assert "delivery_proof" in type_names
        assert "digital_delivery_proof" in type_names

    def test_cancelled_recurring_has_types(self) -> None:
        assert DisputeCondition.CANCELLED_RECURRING in COMPELLING_EVIDENCE_TYPES

    def test_credit_not_processed_has_types(self) -> None:
        assert DisputeCondition.CREDIT_NOT_PROCESSED in COMPELLING_EVIDENCE_TYPES


# ============================================================================
# evaluate_compelling_evidence
# ============================================================================


class TestEvaluateCompellingEvidence:
    """Test the main compelling evidence evaluator."""

    def test_no_condition(self) -> None:
        case = _make_case(condition=None)
        results = evaluate_compelling_evidence(case, [])
        assert len(results) == 1
        assert not results[0].is_compelling

    def test_no_evidence_types_for_condition(self) -> None:
        """Condition with no compelling evidence types defined."""
        case = _make_case(condition=DisputeCondition.DECLINED_AUTHORIZATION)
        results = evaluate_compelling_evidence(case, [])
        assert len(results) == 1
        assert not results[0].is_compelling
        assert "not_applicable" in results[0].evidence_type

    def test_no_acquirer_evidence(self) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        results = evaluate_compelling_evidence(case, [])
        assert len(results) == 1
        assert not results[0].is_compelling
        assert "none_provided" in results[0].evidence_type

    def test_matching_delivery_evidence(self) -> None:
        """Evidence matching delivery_confirmation type is compelling."""
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence(
                "Delivery confirmation to AVS-verified address",
                evidence_type="delivery confirmation",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_matching_previous_transactions(self) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence(
                "Three prior undisputed transactions from same IP address",
                evidence_type="previous undisputed transactions",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_matching_identity_verification(self) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence(
                "3-D Secure authentication completed",
                evidence_type="identity verification via 3DS",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_non_matching_evidence(self) -> None:
        """Evidence that doesn't match any type → not compelling."""
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence(
                "Random unrelated document",
                evidence_type="generic_doc",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert all(not r.is_compelling for r in results)

    def test_non_compelling_evidence_skipped(self) -> None:
        """Evidence with is_compelling_evidence=False is skipped."""
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [_regular_evidence("Delivery proof")]
        results = evaluate_compelling_evidence(case, evidence)
        # Only the "none_provided" result
        assert len(results) == 1
        assert not results[0].is_compelling

    def test_delivery_proof_for_merchandise_not_received(self) -> None:
        case = _make_case(condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED)
        evidence = [
            _compelling_evidence(
                "Proof of delivery signed by cardholder with tracking information",
                evidence_type="delivery proof",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_digital_delivery_for_merchandise(self) -> None:
        case = _make_case(condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED)
        evidence = [
            _compelling_evidence(
                "Digital download access log from cardholder IP",
                evidence_type="digital delivery proof",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_cancellation_evidence_for_recurring(self) -> None:
        case = _make_case(condition=DisputeCondition.CANCELLED_RECURRING)
        evidence = [
            _compelling_evidence(
                "No cancellation record found before transaction date",
                evidence_type="no cancellation record",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_credit_processed_evidence(self) -> None:
        case = _make_case(condition=DisputeCondition.CREDIT_NOT_PROCESSED)
        evidence = [
            _compelling_evidence(
                "Credit already processed on 2026-02-10 with transaction ID TXN-123",
                evidence_type="credit processed evidence",
            ),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        assert any(r.is_compelling for r in results)

    def test_multiple_evidence_mixed(self) -> None:
        """Multiple pieces of evidence → some compelling, some not."""
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence("Delivery proof to verified address", "delivery"),
            _compelling_evidence("Random screenshot", "screenshot"),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        compelling = [r for r in results if r.is_compelling]
        not_compelling = [r for r in results if not r.is_compelling]
        assert len(compelling) >= 1
        assert len(not_compelling) >= 1


# ============================================================================
# _evidence_matches_type helper
# ============================================================================


class TestEvidenceMatchesType:
    """Test the semantic matching helper."""

    def test_delivery_keywords(self) -> None:
        evidence = DisputeEvidence(
            description="Delivery to cardholder address",
            evidence_type="delivery confirmation",
            provided_by="acquirer",
        )
        assert _evidence_matches_type(evidence, "delivery_confirmation")

    def test_chip_keywords(self) -> None:
        evidence = DisputeEvidence(
            description="Full chip data from EMV terminal",
            evidence_type="chip reading",
            provided_by="acquirer",
        )
        assert _evidence_matches_type(evidence, "chip_reading_evidence")

    def test_no_match(self) -> None:
        evidence = DisputeEvidence(
            description="Generic merchant note",
            evidence_type="note",
            provided_by="acquirer",
        )
        assert not _evidence_matches_type(evidence, "delivery_confirmation")


# ============================================================================
# convert_to_rule_evaluation
# ============================================================================


class TestConvertToRuleEvaluation:
    def test_compelling_result_converts(self) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        evidence = [
            _compelling_evidence("Delivery to AVS address", "delivery"),
        ]
        results = evaluate_compelling_evidence(case, evidence)
        for r in results:
            eval_result = convert_to_rule_evaluation(r)
            assert eval_result.rule_id.startswith("compelling_evidence_")
            assert eval_result.rule_section == "11.5.2"
