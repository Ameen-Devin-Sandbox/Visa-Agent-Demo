"""Base agent class with LLM integration and tool execution."""

from __future__ import annotations

import logging
from typing import Any

from src.llm.base import LLMMessage, LLMProvider
from src.models.dispute import Dispute
from src.models.task import DisputeTask, TaskResult
from src.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all dispute processing agents.

    Each agent has:
    - A system prompt defining its role and capabilities
    - Access to the rule engine via tools
    - An LLM for reasoning about complex cases
    """

    agent_name: str = "base"
    system_prompt: str = ""

    def __init__(
        self,
        llm: LLMProvider,
        disputes: dict[str, Dispute],
    ) -> None:
        self._llm = llm
        self._disputes = disputes
        self._tool_executor = ToolExecutor(disputes)

    async def process(self, task: DisputeTask) -> TaskResult:
        """Process a dispute task. Override in subclasses for specific logic."""
        raise NotImplementedError

    async def _reason(self, prompt: str, context: str = "") -> str:
        """Use the LLM to reason about a dispute scenario."""
        messages = []
        if self.system_prompt:
            messages.append(LLMMessage(role="system", content=self.system_prompt))
        if context:
            messages.append(LLMMessage(role="user", content=f"Context:\n{context}"))
        messages.append(LLMMessage(role="user", content=prompt))

        response = await self._llm.complete(messages)
        return response.content

    async def _reason_with_tools(
        self, prompt: str, context: str = "", max_iterations: int = 5
    ) -> str:
        """Use the LLM with tool access for multi-step reasoning."""
        messages: list[LLMMessage] = []
        if self.system_prompt:
            messages.append(LLMMessage(role="system", content=self.system_prompt))
        if context:
            prompt = f"Context:\n{context}\n\nTask:\n{prompt}"
        messages.append(LLMMessage(role="user", content=prompt))

        for _ in range(max_iterations):
            response = await self._llm.complete(messages, temperature=0.1)
            # If the response doesn't request tool use, we're done
            if response.stop_reason != "tool_use":
                return response.content
            # Otherwise the response would need tool call handling
            # For now, return the text content
            return response.content

        return response.content

    def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result."""
        return self._tool_executor.execute(tool_name, args)

    def _format_dispute_summary(self, dispute: Dispute) -> str:
        """Create a human-readable summary of a dispute for LLM context."""
        txn = dispute.transaction
        lines = [
            f"Dispute ID: {dispute.dispute_id}",
            f"Status: {dispute.status}",
            f"Phase: {dispute.phase}",
            f"Category: {dispute.category or 'Not determined'}",
            f"Condition: {dispute.condition or 'Not determined'}",
            "",
            "Transaction Details:",
            f"  Transaction ID: {txn.transaction_id}",
            f"  Date: {txn.transaction_date}",
            f"  Processing Date: {txn.processing_date}",
            f"  Amount: {txn.amount} {txn.currency}",
            f"  Merchant: {txn.merchant_name} (MCC: {txn.merchant_category_code})",
            f"  Environment: {txn.environment}",
            f"  Chip-initiated: {txn.is_chip_initiated}",
            f"  Chip-Reading Device: {txn.is_chip_reading_device}",
            f"  Recurring: {txn.is_recurring}",
            f"  Mobile Push Payment: {txn.is_mobile_push_payment}",
            f"  STP: {txn.is_straight_through_processing}",
            f"  3DS Authenticated: {txn.three_ds_authenticated}",
            f"  ECI: {txn.eci_indicator or 'N/A'}",
            f"  CAVV: {txn.cavv_present}",
            f"  CVV2 Result: {txn.cvv2_result or 'N/A'}",
            f"  Authorization: {txn.authorization_response or 'N/A'}",
            "",
            "Dispute Details:",
            f"  Cardholder Financial Loss: {dispute.cardholder_financial_loss}",
            f"  Fraud Reported to Visa: {dispute.fraud_reported_to_visa}",
            f"  Fraud Type: {dispute.fraud_type or 'N/A'}",
            f"  Cardholder Attempted Resolution: {dispute.cardholder_attempted_resolution}",
            f"  Disputes on Account (120 days): {dispute.disputes_on_account_last_120_days}",
            f"  Prior Credits Applied: {dispute.prior_credits_applied}",
            f"  Evidence Documents: {len(dispute.evidence)}",
            f"  Actions Taken: {len(dispute.actions)}",
        ]
        return "\n".join(lines)
