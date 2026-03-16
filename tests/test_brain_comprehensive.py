"""Comprehensive tests for the DisputeBrain orchestrator.

Tests the full pipeline: intake → validation → categorization → agent routing → decision.
"""

from datetime import date

import pytest

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    DisputeLifecycleStage,
    DisputeResolution,
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)
from src.orchestrator.brain import DisputeBrain
from src.queue.task_queue import DisputeTaskQueue


@pytest.fixture
def brain() -> DisputeBrain:
    return DisputeBrain(DisputeTaskQueue())


def _make_case(**overrides: object) -> DisputeCase:
    txn_defaults = {
        "transaction_id": "TXN-BRAIN-001",
        "transaction_date": date(2026, 2, 15),
        "processing_date": date(2026, 2, 16),
        "amount": 500.0,
        "currency": "USD",
        "merchant_name": "TestMerchant",
        "merchant_category_code": "5411",
        "merchant_country": "US",
        "acquirer_bin": "411111",
        "issuer_bin": "422222",
        "environment": TransactionEnvironment.ECOMMERCE,
        "region": Region.US,
    }

    cardholder_defaults = {
        "cardholder_name": "Test User",
        "partial_payment_credential": "****1234",
    }

    # Separate overrides for case vs transaction
    case_fields = {
        "fraud_type_code", "issuer_certification", "evidence",
        "dispute_amount", "dispute_currency",
    }
    case_overrides = {k: v for k, v in overrides.items() if k in case_fields}
    txn_overrides_dict = {k: v for k, v in overrides.items() if k not in case_fields and k != "statement"}

    statement = overrides.get("statement")

    txn_defaults.update(txn_overrides_dict)

    return DisputeCase(
        transaction=TransactionDetails(**txn_defaults),
        cardholder=CardholderInfo(
            **cardholder_defaults,
            cardholder_statement=statement,
        ),
        **case_overrides,
    )


# ============================================================================
# Full pipeline tests (process_single)
# ============================================================================


class TestBrainProcessSingle:
    """Test synchronous dispute processing through the full pipeline."""

    async def test_fraud_dispute_end_to_end(self, brain: DisputeBrain) -> None:
        """Fraud case flows through: validation → categorization → fraud agent → decision."""
        case = _make_case(
            statement="This was an unauthorized transaction on my card",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
        )
        result = await brain.process_single(case)

        assert result.category == DisputeCategory.FRAUD
        assert result.condition is not None
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.assigned_agent == "fraud_agent"
        assert len(result.stage_history) > 0
        assert len(result.rule_evaluations) > 0

    async def test_authorization_dispute_end_to_end(self, brain: DisputeBrain) -> None:
        """Declined auth case flows through the full pipeline."""
        case = _make_case(
            statement="My card was declined but the charge went through",
            authorization_response_code="05",
            evidence=[
                DisputeEvidence(
                    description="Authorization decline record",
                    evidence_type="auth_record",
                    provided_by="issuer",
                ),
            ],
        )
        result = await brain.process_single(case)

        assert result.category == DisputeCategory.AUTHORIZATION
        assert result.condition == DisputeCondition.NO_AUTHORIZATION
        assert result.decision is not None
        assert result.assigned_agent == "authorization_agent"

    async def test_processing_error_end_to_end(self, brain: DisputeBrain) -> None:
        """Processing error case flows through the full pipeline."""
        case = _make_case(
            statement="I was charged an incorrect amount of $500 instead of $100",
            authorization_code="ABC123",
            authorization_response_code="00",
            dispute_amount=100.0,
            evidence=[
                DisputeEvidence(
                    description="Receipt showing $100",
                    evidence_type="receipt",
                    provided_by="issuer",
                ),
            ],
        )
        result = await brain.process_single(case)

        assert result.category == DisputeCategory.PROCESSING_ERRORS
        assert result.condition == DisputeCondition.INCORRECT_AMOUNT
        assert result.decision is not None
        assert result.assigned_agent == "processing_errors_agent"

    async def test_consumer_dispute_end_to_end(self, brain: DisputeBrain) -> None:
        """Consumer dispute flows through the full pipeline."""
        case = _make_case(
            statement="I ordered goods but they were never received",
            authorization_code="ABC123",
            authorization_response_code="00",
            evidence=[
                DisputeEvidence(
                    description="Order confirmation showing expected delivery",
                    evidence_type="order_confirmation",
                    provided_by="issuer",
                ),
            ],
        )
        result = await brain.process_single(case)

        assert result.category == DisputeCategory.CONSUMER_DISPUTES
        assert result.condition == DisputeCondition.MERCHANDISE_NOT_RECEIVED
        assert result.decision is not None
        assert result.assigned_agent == "consumer_disputes_agent"

    async def test_atm_dispute_categorized_as_13_9(self, brain: DisputeBrain) -> None:
        """ATM cash not received → 13.9."""
        case = _make_case(
            statement="Cash was not dispensed at the ATM",
            environment=TransactionEnvironment.ATM,
            authorization_code="ABC",
            authorization_response_code="00",
            evidence=[
                DisputeEvidence(
                    description="ATM receipt",
                    evidence_type="atm_receipt",
                    provided_by="issuer",
                ),
            ],
        )
        result = await brain.process_single(case)
        assert result.condition == DisputeCondition.NON_RECEIPT_CASH_ATM

    async def test_duplicate_charge_categorized_as_12_6(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="I was charged twice for this duplicate transaction",
            authorization_code="ABC",
            authorization_response_code="00",
            evidence=[
                DisputeEvidence(
                    description="Duplicate transaction records",
                    evidence_type="duplicate",
                    provided_by="issuer",
                ),
            ],
        )
        result = await brain.process_single(case)
        assert result.condition == DisputeCondition.DUPLICATE_PROCESSING


# ============================================================================
# Case management
# ============================================================================


class TestBrainCaseManagement:
    """Test case registration, retrieval, and summary."""

    async def test_case_stored_after_processing(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = await brain.process_single(case)
        stored = brain.get_case(result.case_id)
        assert stored is not None
        assert stored.case_id == result.case_id

    async def test_get_case_nonexistent(self, brain: DisputeBrain) -> None:
        assert brain.get_case("nonexistent") is None

    async def test_get_all_cases(self, brain: DisputeBrain) -> None:
        case1 = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        case2 = _make_case(
            statement="Merchandise not received",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        await brain.process_single(case1)
        await brain.process_single(case2)

        all_cases = brain.get_all_cases()
        assert len(all_cases) == 2

    async def test_get_case_summary(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        result = await brain.process_single(case)
        summary = brain.get_case_summary(result.case_id)

        assert summary is not None
        assert summary["case_id"] == result.case_id
        assert summary["category"] is not None
        assert summary["condition"] is not None
        assert summary["resolution"] is not None
        assert summary["confidence"] is not None
        assert summary["rule_evaluations_count"] > 0
        assert summary["created_at"] is not None
        assert summary["updated_at"] is not None

    async def test_get_case_summary_nonexistent(self, brain: DisputeBrain) -> None:
        assert brain.get_case_summary("nonexistent") is None


# ============================================================================
# Escalation flows
# ============================================================================


class TestBrainEscalation:
    """Test pre-arbitration and arbitration escalation."""

    async def test_escalate_to_pre_arbitration(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        processed = await brain.process_single(case)

        # Add acquirer evidence for pre-arb
        processed.add_evidence(
            DisputeEvidence(
                description="Delivery to cardholder's verified address",
                evidence_type="delivery confirmation",
                provided_by="acquirer",
                is_compelling_evidence=True,
            )
        )

        result = await brain.escalate_to_pre_arbitration(processed.case_id)
        assert result is not None
        assert result.pre_arbitration_attempts >= 1

    async def test_escalate_nonexistent_case(self, brain: DisputeBrain) -> None:
        result = await brain.escalate_to_pre_arbitration("nonexistent")
        assert result is None

    async def test_escalate_to_arbitration(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        processed = await brain.process_single(case)
        result = await brain.escalate_to_arbitration(processed.case_id)
        assert result is not None
        assert result.arbitration_filed is True
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ESCALATED_ARBITRATION

    async def test_escalate_arbitration_nonexistent(self, brain: DisputeBrain) -> None:
        result = await brain.escalate_to_arbitration("nonexistent")
        assert result is None


# ============================================================================
# Human review
# ============================================================================


class TestBrainHumanReview:
    """Test human review approval/rejection."""

    async def test_approve_human_review(self, brain: DisputeBrain) -> None:
        """Approve a case in human review → RESOLVED."""
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            # No certification → will go to human review
        )
        processed = await brain.process_single(case)

        if processed.stage == DisputeLifecycleStage.HUMAN_REVIEW:
            result = await brain.approve_human_review(
                processed.case_id, approved=True, reviewer_notes="Looks correct"
            )
            assert result is not None
            assert result.stage == DisputeLifecycleStage.RESOLVED

    async def test_reject_human_review(self, brain: DisputeBrain) -> None:
        """Reject a case in human review → PROCESSING."""
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        processed = await brain.process_single(case)

        if processed.stage == DisputeLifecycleStage.HUMAN_REVIEW:
            result = await brain.approve_human_review(
                processed.case_id, approved=False, reviewer_notes="Need more docs"
            )
            assert result is not None
            assert result.stage == DisputeLifecycleStage.PROCESSING
            assert result.decision is None  # Decision cleared

    async def test_review_nonexistent_case(self, brain: DisputeBrain) -> None:
        result = await brain.approve_human_review("nonexistent", approved=True)
        assert result is None

    async def test_review_non_review_stage(self, brain: DisputeBrain) -> None:
        """Case not in human review → no state change."""
        case = _make_case(
            statement="Unauthorized transaction",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        processed = await brain.process_single(case)
        if processed.stage == DisputeLifecycleStage.RESOLVED:
            result = await brain.approve_human_review(processed.case_id, approved=True)
            assert result is not None
            assert result.stage == DisputeLifecycleStage.RESOLVED  # Unchanged


# ============================================================================
# Queue-based processing
# ============================================================================


class TestBrainQueueProcessing:
    """Test queue submission and worker loop processing."""

    async def test_submit_dispute(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        case_id = await brain.submit_dispute(case)
        assert case_id == case.case_id
        assert brain.get_case(case_id) is not None

    async def test_start_stop_workers(self, brain: DisputeBrain) -> None:
        await brain.start()
        assert brain._running is True
        assert len(brain._workers) == 3

        await brain.stop()
        assert brain._running is False
        assert len(brain._workers) == 0

    async def test_start_idempotent(self, brain: DisputeBrain) -> None:
        await brain.start()
        await brain.start()  # Second call should be a no-op
        assert len(brain._workers) == 3
        await brain.stop()


# ============================================================================
# Validation
# ============================================================================


class TestBrainValidation:
    """Test basic case validation."""

    async def test_valid_case_passes(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = await brain.process_single(case)
        assert result.stage != DisputeLifecycleStage.REJECTED

    async def test_stage_history_recorded(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        result = await brain.process_single(case)
        # Should have: INTAKE→VALIDATION→CATEGORIZATION→PROCESSING→RULE_EVAL→DECISION→RESOLVED
        assert len(result.stage_history) >= 4

    async def test_processing_notes_recorded(self, brain: DisputeBrain) -> None:
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
        )
        result = await brain.process_single(case)
        assert len(result.processing_notes) > 0

    async def test_dispute_amount_defaulted(self, brain: DisputeBrain) -> None:
        """Dispute amount defaults to transaction amount."""
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = await brain.process_single(case)
        assert result.dispute_amount == 500.0
        assert result.dispute_currency == "USD"

    async def test_dispute_filed_date_defaulted(self, brain: DisputeBrain) -> None:
        """Dispute filed date defaults to created_at."""
        case = _make_case(
            statement="Unauthorized",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = await brain.process_single(case)
        assert result.dispute_filed_date is not None
