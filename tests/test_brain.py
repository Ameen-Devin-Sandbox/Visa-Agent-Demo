"""Tests for the orchestrator brain."""

from datetime import date

import pytest

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    TransactionDetails,
)
from src.models.enums import (
    DisputeLifecycleStage,
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)
from src.orchestrator.brain import DisputeBrain
from src.queue.task_queue import DisputeTaskQueue


def _make_fraud_case() -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-FRAUD-001",
            transaction_date=date(2026, 2, 15),
            processing_date=date(2026, 2, 16),
            amount=1250.00,
            currency="USD",
            merchant_name="SuspiciousStore.com",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Jane Doe",
            partial_payment_credential="****1234",
            cardholder_statement="I did not authorize this transaction.",
            signed_letter_provided=True,
        ),
        fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        issuer_certification="Issuer certifies cardholder denies authorization",
    )


def _make_consumer_case() -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-CONS-001",
            transaction_date=date(2026, 1, 15),
            processing_date=date(2026, 1, 16),
            amount=899.99,
            currency="USD",
            merchant_name="OnlineGadgets.com",
            merchant_category_code="5732",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="455555",
            environment=TransactionEnvironment.ECOMMERCE,
            authorization_code="XYZ789",
            authorization_response_code="00",
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Bob Williams",
            partial_payment_credential="****3456",
            cardholder_statement="I ordered a laptop but it was never received.",
            signed_letter_provided=True,
        ),
    )


@pytest.fixture
def brain() -> DisputeBrain:
    queue = DisputeTaskQueue()
    return DisputeBrain(queue)


class TestDisputeBrain:
    @pytest.mark.asyncio
    async def test_process_fraud_dispute(self, brain: DisputeBrain) -> None:
        case = _make_fraud_case()
        result = await brain.process_single(case)
        assert result.category is not None
        assert result.decision is not None
        assert result.stage in (
            DisputeLifecycleStage.RESOLVED,
            DisputeLifecycleStage.HUMAN_REVIEW,
        )

    @pytest.mark.asyncio
    async def test_process_consumer_dispute(self, brain: DisputeBrain) -> None:
        case = _make_consumer_case()
        result = await brain.process_single(case)
        assert result.category is not None
        assert result.decision is not None

    @pytest.mark.asyncio
    async def test_get_case(self, brain: DisputeBrain) -> None:
        case = _make_fraud_case()
        await brain.process_single(case)
        found = brain.get_case(case.case_id)
        assert found is not None
        assert found.case_id == case.case_id

    @pytest.mark.asyncio
    async def test_get_case_summary(self, brain: DisputeBrain) -> None:
        case = _make_fraud_case()
        await brain.process_single(case)
        summary = brain.get_case_summary(case.case_id)
        assert summary is not None
        assert summary["case_id"] == case.case_id
        assert "stage" in summary
        assert "category" in summary

    @pytest.mark.asyncio
    async def test_get_all_cases(self, brain: DisputeBrain) -> None:
        case1 = _make_fraud_case()
        case2 = _make_consumer_case()
        await brain.process_single(case1)
        await brain.process_single(case2)
        cases = brain.get_all_cases()
        assert len(cases) == 2

    @pytest.mark.asyncio
    async def test_escalate_to_pre_arbitration(self, brain: DisputeBrain) -> None:
        case = _make_fraud_case()
        await brain.process_single(case)
        result = await brain.escalate_to_pre_arbitration(case.case_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_case_rejected(self, brain: DisputeBrain) -> None:
        case = DisputeCase(
            transaction=TransactionDetails(
                transaction_id="",
                transaction_date=date(2026, 1, 1),
                processing_date=date(2026, 1, 2),
                amount=100.00,
                currency="USD",
                merchant_name="Test",
                merchant_category_code="5411",
                merchant_country="US",
                acquirer_bin="411111",
                issuer_bin="422222",
                environment=TransactionEnvironment.ECOMMERCE,
            ),
            cardholder=CardholderInfo(
                cardholder_name="",
                partial_payment_credential="",
            ),
        )
        result = await brain.process_single(case)
        assert result.stage == DisputeLifecycleStage.REJECTED

    @pytest.mark.asyncio
    async def test_nonexistent_case(self, brain: DisputeBrain) -> None:
        result = brain.get_case("nonexistent")
        assert result is None
        summary = brain.get_case_summary("nonexistent")
        assert summary is None
