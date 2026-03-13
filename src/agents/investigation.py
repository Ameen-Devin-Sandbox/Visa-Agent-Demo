"""Investigation agent — evaluates evidence and applies detailed rules."""

from __future__ import annotations

import logging

from src.agents.base import BaseAgent
from src.models.dispute import Dispute
from src.models.enums import TaskType
from src.models.task import DisputeTask, TaskResult
from src.rules.engine import RuleEngine
from src.rules.registry import get_compelling_evidence_for_condition, get_condition_rule

logger = logging.getLogger(__name__)

engine = RuleEngine()


class InvestigationAgent(BaseAgent):
    """Investigates disputes by evaluating evidence, checking invalid conditions,
    and determining the strength of the case."""

    agent_name = "investigation"
    system_prompt = """You are a Visa disputes investigation specialist. Your role is to:
1. Thoroughly evaluate all evidence provided by both parties
2. Check every invalid dispute condition that could block the case
3. Assess the strength of compelling evidence (Table 11-6)
4. Determine if pre-arbitration or arbitration is warranted
5. Identify any documentation gaps

You must be meticulous. A missed invalid condition or overlooked evidence
requirement can result in the dispute being rejected by Visa.

Key investigation areas:
- For 10.4 (Card-Absent Fraud): Check 3DS/ECI/CAVV, CVV2 results, 35-dispute cap, CE 3.0
- For 13.x (Consumer): Verify wait periods, cardholder attempt to resolve, return attempts
- For all fraud: Verify fraud type reporting matches the condition
- Always check regional variations for the specific country pair
"""

    async def process(self, task: DisputeTask) -> TaskResult:
        dispute_id = str(task.dispute_id)
        dispute = self._disputes.get(dispute_id)

        if not dispute:
            return TaskResult(
                success=False,
                decision="BLOCKED",
                reasoning=f"Dispute {dispute_id} not found",
            )

        if task.task_type == TaskType.CHECK_INVALID_CONDITIONS:
            return await self._check_invalid_conditions(dispute)
        elif task.task_type == TaskType.REVIEW_COMPELLING_EVIDENCE:
            return await self._review_compelling_evidence(dispute)
        elif task.task_type == TaskType.CALCULATE_DISPUTE_AMOUNT:
            return await self._calculate_amount(dispute)
        else:
            return TaskResult(
                success=False,
                decision="UNSUPPORTED",
                reasoning=f"Investigation agent does not handle: {task.task_type}",
            )

    async def _check_invalid_conditions(self, dispute: Dispute) -> TaskResult:
        """Check all invalid conditions for the dispute."""
        results = engine.check_invalid_conditions(dispute)

        triggered = [(inv, expl) for inv, is_triggered, expl in results if is_triggered]
        needs_review = [(inv, expl) for inv, is_triggered, expl in results if not is_triggered and "manual" in expl.lower() or "LLM" in expl]
        clear = [(inv, expl) for inv, is_triggered, expl in results if not is_triggered and "manual" not in expl.lower() and "LLM" not in expl]

        if triggered:
            decision = "INVALID_CONDITIONS_FOUND"
            success_note = "Dispute has triggered invalid conditions"
        elif needs_review:
            decision = "REVIEW_NEEDED"
            success_note = f"{len(needs_review)} conditions require manual/LLM review"
        else:
            decision = "ALL_CLEAR"
            success_note = "No invalid conditions triggered"

        # If there are conditions needing review, use LLM
        llm_analysis = ""
        if needs_review:
            summary = self._format_dispute_summary(dispute)
            conditions_text = "\n".join(
                f"  - {inv.condition_id}: {inv.description}" for inv, _ in needs_review
            )
            llm_analysis = await self._reason(
                f"The following invalid dispute conditions could not be evaluated programmatically "
                f"and need your analysis:\n{conditions_text}\n\n"
                "Based on the dispute facts, determine if any of these conditions are triggered. "
                "Be specific about which fields/facts you checked.",
                context=summary,
            )

        return TaskResult(
            success=True,
            decision=decision,
            reasoning=f"{success_note}\n\nTriggered: {len(triggered)}, Clear: {len(clear)}, "
                      f"Needs Review: {len(needs_review)}"
                      + (f"\n\nLLM Analysis:\n{llm_analysis}" if llm_analysis else ""),
            data={
                "triggered": [
                    {"id": inv.condition_id, "description": inv.description, "explanation": expl}
                    for inv, expl in triggered
                ],
                "clear": [
                    {"id": inv.condition_id, "description": inv.description}
                    for inv, _ in clear
                ],
                "needs_review": [
                    {"id": inv.condition_id, "description": inv.description}
                    for inv, _ in needs_review
                ],
            },
            warnings=[f"Invalid condition triggered: {inv.description}" for inv, _ in triggered],
        )

    async def _review_compelling_evidence(self, dispute: Dispute) -> TaskResult:
        """Review compelling evidence options and assess what's available."""
        if dispute.condition is None:
            return TaskResult(
                success=False,
                decision="BLOCKED",
                reasoning="No dispute condition set",
            )

        ce_items = get_compelling_evidence_for_condition(dispute.condition)
        if not ce_items:
            return TaskResult(
                success=True,
                decision="NO_CE_APPLICABLE",
                reasoning=f"Compelling Evidence is not applicable for condition {dispute.condition.value}",
            )

        # Use LLM to assess which CE items might be available based on case facts
        summary = self._format_dispute_summary(dispute)
        ce_text = "\n".join(
            f"  CE #{ce.item_number}: {ce.description}"
            + (f"\n    Sub-requirements: {', '.join(ce.sub_requirements)}" if ce.sub_requirements else "")
            for ce in ce_items
        )

        analysis = await self._reason(
            f"Review the following Compelling Evidence options for condition {dispute.condition.value}:\n"
            f"{ce_text}\n\n"
            "Based on the dispute facts, assess:\n"
            "1. Which CE items are potentially applicable?\n"
            "2. What additional evidence would the Acquirer need to provide?\n"
            "3. How strong is the potential CE case?",
            context=summary,
        )

        return TaskResult(
            success=True,
            decision="CE_REVIEWED",
            reasoning=analysis,
            data={
                "available_ce": [
                    {"item_number": ce.item_number, "description": ce.description}
                    for ce in ce_items
                ],
                "analysis": analysis,
            },
        )

    async def _calculate_amount(self, dispute: Dispute) -> TaskResult:
        """Calculate the dispute amount based on condition rules."""
        if dispute.condition is None:
            return TaskResult(
                success=False,
                decision="BLOCKED",
                reasoning="No dispute condition set",
            )

        rule = get_condition_rule(dispute.condition)
        txn = dispute.transaction

        return TaskResult(
            success=True,
            decision="AMOUNT_CALCULATED",
            reasoning=f"Amount rule: {rule.dispute_amount_rule}\n"
                      f"Transaction amount: {txn.amount} {txn.currency}",
            data={
                "amount_rule": rule.dispute_amount_rule,
                "transaction_amount": str(txn.amount),
                "currency": txn.currency,
                "condition": dispute.condition.value,
            },
        )
