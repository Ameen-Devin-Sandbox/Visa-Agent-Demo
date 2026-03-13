"""Tests for the orchestrator."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.agents.orchestrator import TASK_ROUTING, Orchestrator
from src.config import AppConfig
from src.llm.base import LLMProvider, LLMResponse
from src.models.dispute import Dispute, Party, TransactionDetail
from src.models.enums import (
    DisputeCategory,
    FraudType,
    PartyRole,
    TaskType,
    TransactionEnvironment,
)
from src.queue.memory import InMemoryQueue


class MockLLM(LLMProvider):
    """Mock LLM provider for testing."""

    async def complete(self, messages, temperature=0.1, max_tokens=4096):
        return LLMResponse(
            content="Based on the dispute facts, condition 10.4 (Card-Absent Fraud) is the most appropriate.",
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    async def complete_with_tools(self, messages, tools, temperature=0.1, max_tokens=4096):
        return LLMResponse(
            content="Tool analysis complete.",
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50},
        )


def make_fraud_dispute() -> Dispute:
    return Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-TEST",
            transaction_date=date.today() - timedelta(days=31),
            processing_date=date.today() - timedelta(days=30),
            amount=Decimal("250.00"),
            currency="USD",
            merchant_name="TestMerchant",
            merchant_category_code="5411",
            environment=TransactionEnvironment.ECOMMERCE,
            fraud_type_reported=FraudType.CARD_ABSENT,
        ),
        category=DisputeCategory.FRAUD,
        issuer=Party(role=PartyRole.ISSUER, name="Test Issuer"),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Test Acquirer"),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Test Cardholder"),
        merchant=Party(role=PartyRole.MERCHANT, name="Test Merchant"),
        fraud_reported_to_visa=True,
        fraud_type=FraudType.CARD_ABSENT,
        cardholder_financial_loss=True,
    )


class TestOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        config = AppConfig()
        queue = InMemoryQueue()
        llm = MockLLM()
        return Orchestrator(config=config, queue=queue, llm=llm)

    @pytest.mark.asyncio
    async def test_submit_dispute(self, orchestrator):
        dispute = make_fraud_dispute()
        task_id = await orchestrator.submit_dispute(dispute)
        assert task_id is not None
        assert orchestrator.get_dispute(str(dispute.dispute_id)) is not None

    @pytest.mark.asyncio
    async def test_process_next_determines_condition(self, orchestrator):
        dispute = make_fraud_dispute()
        await orchestrator.submit_dispute(dispute)

        result = await orchestrator.process_next()
        assert result is not None
        assert result.success is True
        assert "10.4" in result.decision or "CONDITION" in result.decision

    @pytest.mark.asyncio
    async def test_process_next_empty_queue(self, orchestrator):
        result = await orchestrator.process_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_full_pipeline(self, orchestrator):
        """Process a dispute through the full pipeline."""
        dispute = make_fraud_dispute()
        await orchestrator.submit_dispute(dispute)

        # Process all tasks
        results = []
        for _ in range(10):
            result = await orchestrator.process_next()
            if result is None:
                break
            results.append(result)

        assert len(results) >= 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_get_dispute_status(self, orchestrator):
        dispute = make_fraud_dispute()
        await orchestrator.submit_dispute(dispute)
        await orchestrator.process_next()

        status = await orchestrator.get_dispute_status(str(dispute.dispute_id))
        assert status["dispute_id"] == str(dispute.dispute_id)
        assert len(status["tasks"]) >= 1

    def test_all_task_types_have_routing(self):
        """Every task type should be routed to an agent."""
        for task_type in TaskType:
            assert task_type in TASK_ROUTING, f"TaskType {task_type} has no routing"
