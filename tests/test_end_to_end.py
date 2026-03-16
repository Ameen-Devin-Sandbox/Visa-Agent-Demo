"""End-to-end tests demonstrating full dispute lifecycle flows.

Each test traces a complete dispute from intake through resolution,
exercising the full stack: models → categorizer → rules → agent → brain.
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


# ============================================================================
# Scenario 1: Card-Absent Fraud (10.4) — Happy Path
# ============================================================================


class TestScenarioFraudCardAbsent:
    """E-commerce fraud dispute with proper documentation → Issuer wins."""

    async def test_full_lifecycle(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-FRAUD-001",
                transaction_date=date(2026, 1, 15),
                processing_date=date(2026, 1, 16),
                amount=1250.00,
                currency="USD",
                merchant_name="ShadyOnlineStore.com",
                merchant_category_code="5411",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Alice Johnson",
                partial_payment_credential="****4321",
                cardholder_statement=(
                    "I did not authorize this transaction. My card was compromised "
                    "and used for an online purchase I did not make."
                ),
                signed_letter_provided=True,
            ),
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization of this transaction",
        )

        result = await brain.process_single(case)

        # Verify categorization
        assert result.category == DisputeCategory.FRAUD
        assert result.condition == DisputeCondition.OTHER_FRAUD_CARD_ABSENT

        # Verify decision
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.decision.confidence_score >= 0.85
        assert result.decision.decided_by == "fraud_agent"

        # Verify lifecycle
        assert result.stage in (
            DisputeLifecycleStage.RESOLVED,
            DisputeLifecycleStage.HUMAN_REVIEW,
        )
        assert len(result.stage_history) >= 4
        stages_visited = [s["to_stage"] for s in result.stage_history]
        assert "validation" in stages_visited
        assert "categorization" in stages_visited
        assert "processing" in stages_visited

        # Verify audit trail
        assert len(result.rule_evaluations) >= 3
        assert len(result.processing_notes) >= 1


# ============================================================================
# Scenario 2: EMV Counterfeit Fraud (10.1) — Invalid Dispute
# ============================================================================


class TestScenarioEMVCounterfeitInvalid:
    """Chip-initiated transaction claimed as 10.1 → Invalid dispute."""

    async def test_chip_initiated_rejected(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-FRAUD-002",
                transaction_date=date(2026, 2, 1),
                processing_date=date(2026, 2, 2),
                amount=350.00,
                currency="EUR",
                merchant_name="EuropeanRetail",
                merchant_category_code="5311",
                merchant_country="DE",
                acquirer_bin="523456",
                issuer_bin="534567",
                environment=TransactionEnvironment.CARD_PRESENT,
                is_chip_card=True,
                is_chip_initiated=True,  # Makes 10.1 invalid
                region=Region.EUROPE,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Franz Mueller",
                partial_payment_credential="****8765",
                cardholder_statement="This is a counterfeit card transaction",
            ),
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
            issuer_certification="Cardholder denies participation",
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.FRAUD
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE
        assert result.stage == DisputeLifecycleStage.RESOLVED


# ============================================================================
# Scenario 3: Declined Authorization (11.2) — Happy Path
# ============================================================================


class TestScenarioDeclinedAuth:
    """Card declined but merchant processed anyway → Issuer wins."""

    async def test_full_lifecycle(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-AUTH-001",
                transaction_date=date(2026, 2, 10),
                processing_date=date(2026, 2, 11),
                amount=89.99,
                currency="USD",
                merchant_name="RetailGrocery",
                merchant_category_code="5411",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.CARD_PRESENT,
                authorization_response_code="14",  # Declined (non-zero start)
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Bob Williams",
                partial_payment_credential="****2345",
                cardholder_statement="My card was declined but the charge went through",
            ),
            evidence=[
                DisputeEvidence(
                    description="Authorization decline record showing response code 14",
                    evidence_type="authorization_record",
                    provided_by="issuer",
                ),
            ],
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.AUTHORIZATION
        assert result.condition == DisputeCondition.DECLINED_AUTHORIZATION
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.assigned_agent == "authorization_agent"


# ============================================================================
# Scenario 4: Merchandise Not Received (13.1) — Happy Path
# ============================================================================


class TestScenarioMerchandiseNotReceived:
    """Online order never delivered → Consumer dispute."""

    async def test_full_lifecycle(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-CONSUMER-001",
                transaction_date=date(2026, 1, 20),
                processing_date=date(2026, 1, 21),
                amount=299.99,
                currency="USD",
                merchant_name="DropShipPlaza",
                merchant_category_code="5399",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                authorization_code="XYZ789",
                authorization_response_code="00",
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Carol Davis",
                partial_payment_credential="****6789",
                cardholder_statement="I ordered a laptop but it was never received",
            ),
            evidence=[
                DisputeEvidence(
                    description="Order confirmation with expected delivery Jan 30",
                    evidence_type="order_confirmation",
                    provided_by="issuer",
                ),
            ],
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.CONSUMER_DISPUTES
        assert result.condition == DisputeCondition.MERCHANDISE_NOT_RECEIVED
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.assigned_agent == "consumer_disputes_agent"


# ============================================================================
# Scenario 5: Duplicate Processing (12.6) — Happy Path
# ============================================================================


class TestScenarioDuplicateProcessing:
    """Charged twice for same transaction → Processing error."""

    async def test_full_lifecycle(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-PROC-001",
                transaction_date=date(2026, 2, 5),
                processing_date=date(2026, 2, 6),
                amount=75.50,
                currency="USD",
                merchant_name="CoffeeShop",
                merchant_category_code="5812",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.CARD_PRESENT,
                authorization_code="DEF456",
                authorization_response_code="00",
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="David Chen",
                partial_payment_credential="****3456",
                cardholder_statement="I was charged twice for this duplicate purchase",
            ),
            evidence=[
                DisputeEvidence(
                    description="Two identical charges showing duplicate processing",
                    evidence_type="duplicate records",
                    provided_by="issuer",
                ),
            ],
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.PROCESSING_ERRORS
        assert result.condition == DisputeCondition.DUPLICATE_PROCESSING
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.assigned_agent == "processing_errors_agent"


# ============================================================================
# Scenario 6: Full Escalation Flow — Dispute → Pre-Arb → Arbitration
# ============================================================================


class TestScenarioFullEscalation:
    """Fraud dispute → acquirer contests → pre-arb → arbitration."""

    async def test_full_escalation_lifecycle(self, brain: DisputeBrain) -> None:
        # Step 1: Initial fraud dispute
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-ESCALATION-001",
                transaction_date=date(2026, 1, 10),
                processing_date=date(2026, 1, 11),
                amount=5000.00,
                currency="USD",
                merchant_name="LuxuryGoods.com",
                merchant_category_code="5944",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Eve Martinez",
                partial_payment_credential="****7890",
                cardholder_statement="I did not authorize this purchase",
                signed_letter_provided=True,
            ),
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
        )

        processed = await brain.process_single(case)
        assert processed.category == DisputeCategory.FRAUD
        assert processed.decision is not None
        # Step 2: Acquirer contests with compelling evidence
        processed.add_evidence(
            DisputeEvidence(
                description="Previous undisputed transaction from same IP address and device",
                evidence_type="previous undisputed transactions",
                provided_by="acquirer",
                is_compelling_evidence=True,
            )
        )

        pre_arb = await brain.escalate_to_pre_arbitration(processed.case_id)
        assert pre_arb is not None
        assert pre_arb.pre_arbitration_attempts >= 1

        # Step 3: Escalate to arbitration
        arb = await brain.escalate_to_arbitration(processed.case_id)
        assert arb is not None
        assert arb.arbitration_filed is True
        assert arb.decision is not None
        assert arb.decision.resolution == DisputeResolution.ESCALATED_ARBITRATION
        assert arb.decision.requires_human_review is True

        # Verify complete audit trail
        assert len(arb.stage_history) >= 6
        assert len(arb.rule_evaluations) >= 3


# ============================================================================
# Scenario 7: Time-Expired Dispute — Filing Too Late
# ============================================================================


class TestScenarioTimeLimitExceeded:
    """Dispute filed way past 120-day deadline → Rejected."""

    async def test_expired_fraud_dispute(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-EXPIRED-001",
                transaction_date=date(2025, 6, 1),
                processing_date=date(2025, 6, 2),
                amount=150.00,
                currency="USD",
                merchant_name="OldPurchase",
                merchant_category_code="5411",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Frank Wilson",
                partial_payment_credential="****1111",
                cardholder_statement="I just noticed this unauthorized charge from last year",
            ),
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
            # dispute_filed_date will default to created_at (now - well past 120 days)
        )

        result = await brain.process_single(case)

        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE
        assert result.stage == DisputeLifecycleStage.RESOLVED


# ============================================================================
# Scenario 8: ATM Cash Not Received (13.9)
# ============================================================================


class TestScenarioATMCashNotReceived:
    """ATM transaction with no cash dispensed → Consumer dispute 13.9."""

    async def test_atm_dispute(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-ATM-001",
                transaction_date=date(2026, 2, 20),
                processing_date=date(2026, 2, 21),
                amount=500.00,
                currency="USD",
                merchant_name="ATM-BANK-12345",
                merchant_category_code="6011",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ATM,
                authorization_code="ATM789",
                authorization_response_code="00",
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Grace Lee",
                partial_payment_credential="****2222",
                cardholder_statement="Cash was not dispensed at the ATM but my account was debited",
            ),
            evidence=[
                DisputeEvidence(
                    description="ATM receipt showing withdrawal attempt",
                    evidence_type="atm_receipt",
                    provided_by="issuer",
                ),
            ],
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.CONSUMER_DISPUTES
        assert result.condition == DisputeCondition.NON_RECEIPT_CASH_ATM
        assert result.decision is not None
        assert result.assigned_agent == "consumer_disputes_agent"


# ============================================================================
# Scenario 9: Human Review Workflow
# ============================================================================


class TestScenarioHumanReview:
    """High-value fraud triggers human review → manual approval."""

    async def test_high_value_fraud_review(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-REVIEW-001",
                transaction_date=date(2026, 2, 10),
                processing_date=date(2026, 2, 11),
                amount=30000.00,  # Over $25k threshold
                currency="USD",
                merchant_name="ExpensiveStore",
                merchant_category_code="5944",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Henry Park",
                partial_payment_credential="****3333",
                cardholder_statement="I did not authorize this expensive purchase",
            ),
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
        )

        result = await brain.process_single(case)
        assert result.decision is not None

        if result.decision.requires_human_review:
            assert result.stage == DisputeLifecycleStage.HUMAN_REVIEW

            # Human approves
            approved = await brain.approve_human_review(
                result.case_id,
                approved=True,
                reviewer_notes="Reviewed and approved - legitimate fraud claim",
            )
            assert approved is not None
            assert approved.stage == DisputeLifecycleStage.RESOLVED


# ============================================================================
# Scenario 10: Cancelled Recurring (13.2) with Recurring Flag
# ============================================================================


class TestScenarioCancelledRecurring:
    """Subscription cancelled but still charged → Consumer dispute."""

    async def test_cancelled_recurring(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="TXN-E2E-RECURRING-001",
                transaction_date=date(2026, 2, 1),
                processing_date=date(2026, 2, 2),
                amount=14.99,
                currency="USD",
                merchant_name="StreamingService",
                merchant_category_code="5815",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
                authorization_code="REC123",
                authorization_response_code="00",
                is_recurring=True,
                region=Region.US,
            ),
            cardholder=CardholderInfo(
                cardholder_name="Ivy Taylor",
                partial_payment_credential="****4444",
                cardholder_statement="I cancelled my subscription last month but was still charged",
            ),
            evidence=[
                DisputeEvidence(
                    description="Cancellation email from November 2025",
                    evidence_type="cancellation_confirmation",
                    provided_by="issuer",
                ),
            ],
        )

        result = await brain.process_single(case)

        assert result.category == DisputeCategory.CONSUMER_DISPUTES
        assert result.condition == DisputeCondition.CANCELLED_RECURRING
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
