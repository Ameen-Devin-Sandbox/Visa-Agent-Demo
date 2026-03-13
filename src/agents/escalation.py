"""Escalation agent — handles arbitration and compliance proceedings."""

from __future__ import annotations

import logging

from src.agents.base import BaseAgent
from src.models.dispute import Dispute
from src.models.enums import DisputePhase, DisputeStatus, TaskType
from src.models.task import DisputeTask, TaskResult
from src.rules.engine import RuleEngine

logger = logging.getLogger(__name__)

engine = RuleEngine()


class EscalationAgent(BaseAgent):
    """Handles arbitration and compliance escalation."""

    agent_name = "escalation"
    system_prompt = """You are a Visa disputes escalation specialist handling Arbitration and Compliance.

ARBITRATION (Section 11.11-11.13):
- Filed when the dispute/pre-arb cycle is completed and unresolved
- Time limit: 10 calendar days from pre-arb response Processing Date
- All documentation in English
- Max 10 disputed transactions per case (same credential, Acquirer, Merchant, condition)
- Must NOT submit documents not previously given to opposing Member
- Decision is based on all available information and Visa Rules effective on Transaction Date
- Visa may issue split decisions for reasonable compromise
- Decision is FINAL (appeal only if new evidence + amount >= USD 5,000)

COMPLIANCE (Section 11.12):
- Filed when a Visa Rules violation occurred and no dispute/response/pre-arb right exists
- Must make pre-Compliance attempt >= 30 calendar days before filing
- All other filings: 90 cal days from Processing Date/violation/discovery (max 2 years from Transaction Date)
- Member must have incurred financial loss as direct result of violation (except surcharge)
- Decision is FINAL

APPEAL:
- Only if new evidence not previously available AND amount >= USD 5,000
- 60 calendar days from decision notification
- Appeal decision is FINAL
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

        if task.task_type == TaskType.PREPARE_ARBITRATION:
            return await self._prepare_arbitration(dispute)
        elif task.task_type == TaskType.PREPARE_COMPLIANCE:
            return await self._prepare_compliance(dispute)
        else:
            return TaskResult(
                success=False,
                decision="UNSUPPORTED",
                reasoning=f"Escalation agent does not handle: {task.task_type}",
            )

    async def _prepare_arbitration(self, dispute: Dispute) -> TaskResult:
        """Prepare an arbitration filing."""
        summary = self._format_dispute_summary(dispute)

        # Check prerequisites
        issues = []
        if len(dispute.actions) < 2:
            issues.append("Dispute/pre-arb cycle may not be complete")

        if dispute.disputes_on_account_last_120_days > 10:
            issues.append("Warning: High dispute volume on this account")

        analysis = await self._reason(
            "Prepare an Arbitration filing for this dispute. Address:\n"
            "1. Is the dispute/pre-arb cycle properly completed?\n"
            "2. What is the filing basis (cycle complete vs. Visa Rules violation)?\n"
            "3. Prepare the VROL Questionnaire information\n"
            "4. List all supporting documentation (must have been previously shared)\n"
            "5. Confirm all documentation is in English\n"
            "6. Assess the likely outcome\n"
            "7. Note: max 10 transactions per case\n"
            "8. Note: 10 calendar days from pre-arb response Processing Date to file"
            + (f"\n\nIssues to address: {'; '.join(issues)}" if issues else ""),
            context=summary,
        )

        dispute.phase = DisputePhase.ARBITRATION
        dispute.status = DisputeStatus.IN_ARBITRATION

        return TaskResult(
            success=True,
            decision="ARBITRATION_PREPARED",
            reasoning=analysis,
            data={
                "filing_type": "arbitration",
                "issues": issues,
                "analysis": analysis,
            },
            rule_references=["Section 11.11", "Section 11.13"],
        )

    async def _prepare_compliance(self, dispute: Dispute) -> TaskResult:
        """Prepare a compliance filing."""
        summary = self._format_dispute_summary(dispute)

        analysis = await self._reason(
            "Evaluate whether a Compliance filing is appropriate for this dispute. Check:\n"
            "1. Did a Visa Rules violation occur (not Account Data Compromise)?\n"
            "2. Does the Member have no Dispute/Response/Pre-Arb right available?\n"
            "3. Did the Member incur financial loss as a direct result?\n"
            "4. Would the loss not have occurred without the violation?\n"
            "5. Has a pre-Compliance attempt been made (>= 30 cal days before)?\n"
            "6. Which Compliance condition (Tables 11-148 through 11-156) applies?\n"
            "7. Is this within the 90-day filing window (max 2 years from Transaction Date)?\n"
            "If a surcharge violation (Section 11.12.4): no financial loss required, "
            "but only Canada/US/US Territories.",
            context=summary,
        )

        dispute.phase = DisputePhase.COMPLIANCE
        dispute.status = DisputeStatus.IN_COMPLIANCE

        return TaskResult(
            success=True,
            decision="COMPLIANCE_EVALUATED",
            reasoning=analysis,
            data={"analysis": analysis},
            rule_references=["Section 11.12"],
        )
