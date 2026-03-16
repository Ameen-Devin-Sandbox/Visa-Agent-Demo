"""Comprehensive tests for all dispute processing sub-agents.

Tests FraudDisputeAgent, AuthorizationDisputeAgent, ProcessingErrorsAgent,
ConsumerDisputesAgent, and PreArbitrationAgent.
"""

from datetime import date, datetime, timedelta

import pytest

from src.agents.authorization_agent import AuthorizationDisputeAgent
from src.agents.consumer_disputes_agent import ConsumerDisputesAgent
from src.agents.fraud_agent import FraudDisputeAgent
from src.agents.pre_arbitration_agent import PreArbitrationAgent
from src.agents.processing_errors_agent import ProcessingErrorsAgent
from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeCondition,
    DisputeLifecycleStage,
    DisputeResolution,
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)


def _make_case(
    condition: DisputeCondition | None = None,
    category: DisputeCategory | None = None,
    fraud_type_code: FraudTypeCode | None = None,
    statement: str | None = None,
    signed_letter: bool = False,
    issuer_certification: str | None = None,
    evidence: list[DisputeEvidence] | None = None,
    stage: DisputeLifecycleStage = DisputeLifecycleStage.PROCESSING,
    dispute_filed_date: datetime | None = None,
    dispute_amount: float | None = None,
    dispute_currency: str | None = None,
    prior_credits: list[dict[str, float]] | None = None,
    **txn_overrides: object,
) -> DisputeCase:
    txn_defaults = {
        "transaction_id": "TXN-AGENT-001",
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
    txn_defaults.update(txn_overrides)

    return DisputeCase(
        transaction=TransactionDetails(**txn_defaults),
        cardholder=CardholderInfo(
            cardholder_name="Test User",
            partial_payment_credential="****1234",
            cardholder_statement=statement,
            signed_letter_provided=signed_letter,
        ),
        condition=condition,
        category=category,
        fraud_type_code=fraud_type_code,
        issuer_certification=issuer_certification,
        evidence=evidence or [],
        stage=stage,
        dispute_filed_date=dispute_filed_date,
        dispute_amount=dispute_amount,
        dispute_currency=dispute_currency,
        prior_credits=prior_credits or [],
    )


# ============================================================================
# FraudDisputeAgent
# ============================================================================


class TestFraudDisputeAgent:
    """Test Category 10 fraud agent."""

    @pytest.fixture
    def agent(self) -> FraudDisputeAgent:
        return FraudDisputeAgent()

    async def test_agent_type(self, agent: FraudDisputeAgent) -> None:
        assert agent.agent_type == AgentType.FRAUD

    async def test_validate_fraud_condition(self, agent: FraudDisputeAgent) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        assert await agent.validate(case) is True

    async def test_validate_non_fraud_condition(self, agent: FraudDisputeAgent) -> None:
        case = _make_case(condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED)
        assert await agent.validate(case) is False

    async def test_validate_no_condition(self, agent: FraudDisputeAgent) -> None:
        case = _make_case(condition=None)
        assert await agent.validate(case) is False

    async def test_process_valid_fraud(self, agent: FraudDisputeAgent) -> None:
        """Complete fraud case with all docs → ISSUER_WIN, RESOLVED."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.decision.confidence_score >= 0.85
        assert result.stage == DisputeLifecycleStage.RESOLVED
        assert result.assigned_agent == "fraud_agent"

    async def test_process_fraud_time_exceeded(self, agent: FraudDisputeAgent) -> None:
        """Filing after time limit → INVALID_DISPUTE."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            dispute_filed_date=datetime(2026, 2, 16) + timedelta(days=200),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE
        assert result.stage == DisputeLifecycleStage.RESOLVED

    async def test_process_fraud_invalid_validity(self, agent: FraudDisputeAgent) -> None:
        """Chip-initiated 10.1 → invalid validity check."""
        case = _make_case(
            condition=DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
            issuer_certification="Denial",
            dispute_filed_date=datetime(2026, 2, 17),
            environment=TransactionEnvironment.CARD_PRESENT,
            is_chip_initiated=True,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE

    async def test_process_fraud_missing_docs(self, agent: FraudDisputeAgent) -> None:
        """Missing documentation → HUMAN_REVIEW."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            # No certification, no fraud type code
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.requires_human_review is True
        assert result.stage == DisputeLifecycleStage.HUMAN_REVIEW

    async def test_process_fraud_records_evaluations(self, agent: FraudDisputeAgent) -> None:
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Denial",
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert len(result.rule_evaluations) > 0
        rule_ids = [r.rule_id for r in result.rule_evaluations]
        assert "time_limit_check" in rule_ids
        assert "documentation_check" in rule_ids
        assert "fraud_type_code_check" in rule_ids

    async def test_process_fraud_high_value_escalated(self, agent: FraudDisputeAgent) -> None:
        """High-value dispute (>$25k) → escalated to human review."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
            dispute_filed_date=datetime(2026, 2, 17),
            dispute_amount=30000.0,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.requires_human_review is True


# ============================================================================
# AuthorizationDisputeAgent
# ============================================================================


class TestAuthorizationDisputeAgent:
    """Test Category 11 authorization agent."""

    @pytest.fixture
    def agent(self) -> AuthorizationDisputeAgent:
        return AuthorizationDisputeAgent()

    async def test_agent_type(self, agent: AuthorizationDisputeAgent) -> None:
        assert agent.agent_type == AgentType.AUTHORIZATION

    async def test_validate_auth_condition(self, agent: AuthorizationDisputeAgent) -> None:
        case = _make_case(condition=DisputeCondition.DECLINED_AUTHORIZATION)
        assert await agent.validate(case) is True

    async def test_validate_non_auth_condition(self, agent: AuthorizationDisputeAgent) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        assert await agent.validate(case) is False

    async def test_process_declined_auth_valid(self, agent: AuthorizationDisputeAgent) -> None:
        """Declined auth with evidence → ISSUER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Decline response record showing code 14",
                evidence_type="authorization_record",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.DECLINED_AUTHORIZATION,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            authorization_response_code="14",  # Non-zero start = declined
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_declined_auth_actually_approved(
        self, agent: AuthorizationDisputeAgent
    ) -> None:
        """Declined auth claim but response shows approved → ACQUIRER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Auth record",
                evidence_type="authorization_record",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.DECLINED_AUTHORIZATION,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            authorization_response_code="00",  # Approved!
        )
        result = await agent.process(case)
        assert result.decision is not None
        # The validity check should catch this (code starts with 0)
        # OR the auth-specific check will catch it
        # Either way, the dispute should be rejected or acquirer wins
        assert result.decision.resolution in (
            DisputeResolution.INVALID_DISPUTE,
            DisputeResolution.ACQUIRER_WIN,
        )

    async def test_process_no_auth_valid(self, agent: AuthorizationDisputeAgent) -> None:
        """No authorization code → ISSUER_WIN."""
        evidence = [
            DisputeEvidence(
                description="No authorization record found",
                evidence_type="authorization_record",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.NO_AUTHORIZATION,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            authorization_code=None,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_no_auth_but_code_exists(
        self, agent: AuthorizationDisputeAgent
    ) -> None:
        """No auth claim but valid code exists → auth exists is invalid."""
        evidence = [
            DisputeEvidence(
                description="Auth record",
                evidence_type="auth",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.NO_AUTHORIZATION,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            authorization_code="ABC123",
        )
        result = await agent.process(case)
        assert result.decision is not None
        # 11.3 validity check: auth code exists → invalid dispute
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE

    async def test_process_crb_with_evidence(self, agent: AuthorizationDisputeAgent) -> None:
        """Card Recovery Bulletin with CRB evidence → ISSUER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Card Recovery Bulletin listing",
                evidence_type="CRB listing",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.CARD_RECOVERY_BULLETIN,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_crb_without_evidence(self, agent: AuthorizationDisputeAgent) -> None:
        """Card Recovery Bulletin without CRB evidence → ACQUIRER_WIN."""
        case = _make_case(
            condition=DisputeCondition.CARD_RECOVERY_BULLETIN,
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ACQUIRER_WIN

    async def test_time_limit_exceeded(self, agent: AuthorizationDisputeAgent) -> None:
        case = _make_case(
            condition=DisputeCondition.DECLINED_AUTHORIZATION,
            dispute_filed_date=datetime(2026, 2, 16) + timedelta(days=200),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE


# ============================================================================
# ProcessingErrorsAgent
# ============================================================================


class TestProcessingErrorsAgent:
    """Test Category 12 processing errors agent."""

    @pytest.fixture
    def agent(self) -> ProcessingErrorsAgent:
        return ProcessingErrorsAgent()

    async def test_agent_type(self, agent: ProcessingErrorsAgent) -> None:
        assert agent.agent_type == AgentType.PROCESSING_ERRORS

    async def test_validate_processing_error(self, agent: ProcessingErrorsAgent) -> None:
        case = _make_case(condition=DisputeCondition.INCORRECT_AMOUNT)
        assert await agent.validate(case) is True

    async def test_validate_non_processing_error(self, agent: ProcessingErrorsAgent) -> None:
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT)
        assert await agent.validate(case) is False

    async def test_process_incorrect_amount(self, agent: ProcessingErrorsAgent) -> None:
        """Incorrect amount with evidence → ISSUER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Receipt showing correct amount $100",
                evidence_type="receipt",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.INCORRECT_AMOUNT,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            dispute_amount=100.0,  # Different from txn amount of 500.0
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_incorrect_amount_no_evidence(
        self, agent: ProcessingErrorsAgent
    ) -> None:
        """Incorrect amount without amount difference → ACQUIRER_WIN."""
        case = _make_case(
            condition=DisputeCondition.INCORRECT_AMOUNT,
            dispute_filed_date=datetime(2026, 2, 17),
            dispute_amount=None,  # No disputed amount
        )
        result = await agent.process(case)
        assert result.decision is not None
        # Should be invalid or acquirer win since no dispute amount specified
        # Validity check for 12.5 requires dispute_amount
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE

    async def test_process_duplicate_with_evidence(self, agent: ProcessingErrorsAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Duplicate transaction reference",
                evidence_type="duplicate processing record",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.DUPLICATE_PROCESSING,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_incorrect_currency(self, agent: ProcessingErrorsAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Evidence of EUR currency expectation",
                evidence_type="currency_evidence",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.INCORRECT_CURRENCY,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            dispute_currency="EUR",  # Different from USD
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_time_limit_exceeded(self, agent: ProcessingErrorsAgent) -> None:
        case = _make_case(
            condition=DisputeCondition.INCORRECT_AMOUNT,
            dispute_filed_date=datetime(2026, 2, 16) + timedelta(days=200),
            dispute_amount=100.0,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE


# ============================================================================
# ConsumerDisputesAgent
# ============================================================================


class TestConsumerDisputesAgent:
    """Test Category 13 consumer disputes agent."""

    @pytest.fixture
    def agent(self) -> ConsumerDisputesAgent:
        return ConsumerDisputesAgent()

    async def test_agent_type(self, agent: ConsumerDisputesAgent) -> None:
        assert agent.agent_type == AgentType.CONSUMER_DISPUTES

    async def test_validate_consumer_condition(self, agent: ConsumerDisputesAgent) -> None:
        case = _make_case(condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED)
        assert await agent.validate(case) is True

    async def test_validate_non_consumer_condition(self, agent: ConsumerDisputesAgent) -> None:
        case = _make_case(condition=DisputeCondition.DECLINED_AUTHORIZATION)
        assert await agent.validate(case) is False

    async def test_process_merchandise_not_received(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Order receipt for undelivered goods",
                evidence_type="receipt",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            evidence=evidence,
            statement="I never received my order",
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_cancelled_recurring(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Cancellation email confirmation",
                evidence_type="cancellation",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.CANCELLED_RECURRING,
            evidence=evidence,
            statement="I cancelled my subscription",
            dispute_filed_date=datetime(2026, 2, 17),
            is_recurring=True,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_cancelled_recurring_not_recurring(
        self, agent: ConsumerDisputesAgent
    ) -> None:
        """Transaction not flagged as recurring → ACQUIRER_WIN."""
        case = _make_case(
            condition=DisputeCondition.CANCELLED_RECURRING,
            statement="I cancelled my subscription",
            dispute_filed_date=datetime(2026, 2, 17),
            is_recurring=False,
        )
        result = await agent.process(case)
        assert result.decision is not None
        # Validity or specific check should catch this
        assert result.decision.resolution in (
            DisputeResolution.INVALID_DISPUTE,
            DisputeResolution.ACQUIRER_WIN,
        )

    async def test_process_not_as_described(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Product was defective upon arrival",
                evidence_type="description_mismatch",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.NOT_AS_DESCRIBED,
            evidence=evidence,
            statement="The product was completely different",
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_counterfeit_merchandise(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Counterfeit product report from brand",
                evidence_type="counterfeit_evidence",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.COUNTERFEIT_MERCHANDISE,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_credit_not_processed(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="Merchant promised refund but not received",
                evidence_type="credit_claim",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.CREDIT_NOT_PROCESSED,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            prior_credits=[{"amount": 100.0}],
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_process_atm_cash_not_received(self, agent: ConsumerDisputesAgent) -> None:
        evidence = [
            DisputeEvidence(
                description="ATM receipt showing withdrawal but no cash",
                evidence_type="atm_receipt",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.NON_RECEIPT_CASH_ATM,
            evidence=evidence,
            dispute_filed_date=datetime(2026, 2, 17),
            environment=TransactionEnvironment.ATM,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN

    async def test_time_limit_exceeded(self, agent: ConsumerDisputesAgent) -> None:
        case = _make_case(
            condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            dispute_filed_date=datetime(2026, 2, 16) + timedelta(days=200),
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.INVALID_DISPUTE


# ============================================================================
# PreArbitrationAgent
# ============================================================================


class TestPreArbitrationAgent:
    """Test pre-arbitration and arbitration agent."""

    @pytest.fixture
    def agent(self) -> PreArbitrationAgent:
        return PreArbitrationAgent()

    async def test_agent_type(self, agent: PreArbitrationAgent) -> None:
        assert agent.agent_type == AgentType.PRE_ARBITRATION

    async def test_validate_pre_arb_stage(self, agent: PreArbitrationAgent) -> None:
        case = _make_case(stage=DisputeLifecycleStage.PRE_ARBITRATION)
        assert await agent.validate(case) is True

    async def test_validate_arb_stage(self, agent: PreArbitrationAgent) -> None:
        case = _make_case(stage=DisputeLifecycleStage.ARBITRATION)
        assert await agent.validate(case) is True

    async def test_validate_non_arb_stage(self, agent: PreArbitrationAgent) -> None:
        case = _make_case(stage=DisputeLifecycleStage.PROCESSING)
        assert await agent.validate(case) is False

    async def test_pre_arb_with_compelling_evidence(self, agent: PreArbitrationAgent) -> None:
        """Compelling evidence → advance to PRE_ARBITRATION_RESPONSE."""
        evidence = [
            DisputeEvidence(
                description="Delivery proof to AVS-verified address",
                evidence_type="delivery confirmation",
                provided_by="acquirer",
                is_compelling_evidence=True,
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            evidence=evidence,
            stage=DisputeLifecycleStage.PRE_ARBITRATION,
        )
        result = await agent.process(case)
        assert result.stage == DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE
        assert result.pre_arbitration_attempts == 1

    async def test_pre_arb_cardholder_withdrew(self, agent: PreArbitrationAgent) -> None:
        """Cardholder withdrew → WITHDRAWN resolution."""
        evidence = [
            DisputeEvidence(
                description="Cardholder no longer disputes this transaction",
                evidence_type="withdrawal",
                provided_by="acquirer",
                is_compelling_evidence=False,
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            category=DisputeCategory.CONSUMER_DISPUTES,
            evidence=evidence,
            stage=DisputeLifecycleStage.PRE_ARBITRATION,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.WITHDRAWN
        assert result.stage == DisputeLifecycleStage.RESOLVED

    async def test_pre_arb_no_grounds(self, agent: PreArbitrationAgent) -> None:
        """No valid pre-arb grounds → ISSUER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Generic merchant statement",
                evidence_type="statement",
                provided_by="acquirer",
                is_compelling_evidence=False,
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            evidence=evidence,
            stage=DisputeLifecycleStage.PRE_ARBITRATION,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ISSUER_WIN
        assert result.stage == DisputeLifecycleStage.RESOLVED

    async def test_pre_arb_credit_not_addressed(self, agent: PreArbitrationAgent) -> None:
        """Credit not addressed → advance to response stage."""
        evidence = [
            DisputeEvidence(
                description="Credit was not addressed in the dispute",
                evidence_type="credit_claim",
                provided_by="acquirer",
                is_compelling_evidence=False,
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.CREDIT_NOT_PROCESSED,
            category=DisputeCategory.CONSUMER_DISPUTES,
            evidence=evidence,
            stage=DisputeLifecycleStage.PRE_ARBITRATION,
        )
        result = await agent.process(case)
        assert result.stage == DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE

    async def test_pre_arb_response_accepted(self, agent: PreArbitrationAgent) -> None:
        """Issuer accepts responsibility → ACQUIRER_WIN."""
        evidence = [
            DisputeEvidence(
                description="Issuer accepts financial responsibility for this dispute",
                evidence_type="acceptance",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            evidence=evidence,
            stage=DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ACQUIRER_WIN
        assert result.stage == DisputeLifecycleStage.RESOLVED

    async def test_pre_arb_response_with_certification(self, agent: PreArbitrationAgent) -> None:
        """Issuer provides certification → ESCALATED_ARBITRATION."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            issuer_certification="Cardholder still disputes after reviewing evidence",
            stage=DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ESCALATED_ARBITRATION
        assert result.decision.requires_human_review is True

    async def test_pre_arb_response_inadequate(self, agent: PreArbitrationAgent) -> None:
        """Issuer provides no adequate response → ACQUIRER_WIN."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            stage=DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ACQUIRER_WIN

    async def test_arbitration_filing(self, agent: PreArbitrationAgent) -> None:
        """Arbitration → ESCALATED_ARBITRATION with human review."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            stage=DisputeLifecycleStage.ARBITRATION,
        )
        result = await agent.process(case)
        assert result.decision is not None
        assert result.decision.resolution == DisputeResolution.ESCALATED_ARBITRATION
        assert result.decision.requires_human_review is True
        assert result.arbitration_filed is True
        assert result.stage == DisputeLifecycleStage.HUMAN_REVIEW
