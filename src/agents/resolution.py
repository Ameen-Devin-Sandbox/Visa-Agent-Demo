"""Resolution agent — determines outcomes and prepares dispute filings."""

from __future__ import annotations

import logging
from datetime import date, datetime

from src.agents.base import BaseAgent
from src.models.dispute import Dispute, DisputeAction
from src.models.enums import DisputePhase, DisputeStatus, PartyRole, TaskType
from src.models.task import DisputeTask, TaskResult
from src.rules.engine import RuleEngine
from src.rules.registry import get_condition_rule

logger = logging.getLogger(__name__)

engine = RuleEngine()


class ResolutionAgent(BaseAgent):
    """Handles dispute resolution: filing, responding, and closing disputes."""

    agent_name = "resolution"
    system_prompt = """You are a Visa disputes resolution specialist. Your role is to:
1. Prepare and file disputes through VROL
2. Evaluate dispute responses from the opposing party
3. Determine the next appropriate action in the dispute lifecycle
4. Prepare pre-arbitration attempts or responses
5. Calculate final financial liability

Key resolution principles:
- All dispute processing must go through VROL
- Financial messages must be processed on the same day as VROL actions
- A Member that doesn't respond within the timeframe loses by default
- The dispute amount must not exceed the transaction amount (except 12.2)
- Surcharges must be pro-rated in partial disputes
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

        if task.task_type == TaskType.FILE_DISPUTE:
            return await self._file_dispute(dispute)
        elif task.task_type == TaskType.EVALUATE_RESPONSE:
            return await self._evaluate_response(dispute, task)
        elif task.task_type == TaskType.PREPARE_PRE_ARBITRATION:
            return await self._prepare_pre_arbitration(dispute, task)
        elif task.task_type == TaskType.EVALUATE_PRE_ARBITRATION:
            return await self._evaluate_pre_arbitration(dispute, task)
        else:
            return TaskResult(
                success=False,
                decision="UNSUPPORTED",
                reasoning=f"Resolution agent does not handle: {task.task_type}",
            )

    async def _file_dispute(self, dispute: Dispute) -> TaskResult:
        """Prepare and file a dispute."""
        if dispute.status != DisputeStatus.ELIGIBLE:
            return TaskResult(
                success=False,
                decision="NOT_ELIGIBLE",
                reasoning=f"Dispute status is {dispute.status}, not ELIGIBLE",
            )

        rule = get_condition_rule(dispute.condition)
        deadlines = engine.calculate_deadlines(dispute)

        # Check if we need to wait
        if deadlines.wait_until and deadlines.wait_until > date.today():
            return TaskResult(
                success=True,
                decision="MUST_WAIT",
                reasoning=f"Cannot file yet. Wait period until {deadlines.wait_until} "
                          f"({rule.time_limit.wait_days_before} calendar days).",
                data={"wait_until": str(deadlines.wait_until)},
                warnings=[f"Filing blocked until {deadlines.wait_until}"],
            )

        # Prepare the filing
        filing_details = {
            "condition_code": dispute.condition.value,
            "condition_name": rule.name,
            "dispute_amount": str(dispute.dispute_amount or dispute.transaction.amount),
            "currency": dispute.dispute_currency,
            "filing_deadline": str(deadlines.dispute_deadline),
            "required_documentation": [d.description for d in rule.documentation_requirements if d.is_mandatory],
            "financial_message": "Dispute Financial for dispute amount",
            "vrol_submission": True,
        }

        # Determine response flow
        if dispute.uses_dispute_response_flow:
            next_phase = "Awaiting Dispute Response from Acquirer (30 calendar days)"
        else:
            next_phase = "Awaiting Pre-Arbitration Attempt from Acquirer (30 calendar days)"

        # Record the filing action
        action = DisputeAction(
            phase=DisputePhase.DISPUTE_FILED,
            actor=PartyRole.ISSUER,
            action_type="filed",
            processing_date=date.today(),
            amount=dispute.dispute_amount or dispute.transaction.amount,
            currency=dispute.dispute_currency,
            description=f"Dispute filed under condition {dispute.condition.value}: {rule.name}",
        )
        dispute.actions.append(action)
        dispute.phase = DisputePhase.DISPUTE_FILED
        dispute.status = DisputeStatus.FILED
        dispute.updated_at = datetime.utcnow()

        return TaskResult(
            success=True,
            decision="DISPUTE_FILED",
            reasoning=f"Dispute filed under condition {dispute.condition.value} ({rule.name}). "
                      f"Amount: {filing_details['dispute_amount']} {filing_details['currency']}. "
                      f"Next: {next_phase}",
            data=filing_details,
            next_actions=[TaskType.EVALUATE_RESPONSE],
            rule_references=[f"Section {rule.rule_section}"],
        )

    async def _evaluate_response(self, dispute: Dispute, task: DisputeTask) -> TaskResult:
        """Evaluate a response (Dispute Response or Pre-Arb Attempt) from the Acquirer."""
        response_data = task.payload

        summary = self._format_dispute_summary(dispute)
        response_text = "\n".join(f"  {k}: {v}" for k, v in response_data.items())

        analysis = await self._reason(
            f"Evaluate the following {'Dispute Response' if dispute.uses_dispute_response_flow else 'Pre-Arbitration Attempt'} "
            f"from the Acquirer:\n{response_text}\n\n"
            "Determine:\n"
            "1. Is the response valid and timely?\n"
            "2. Does the evidence provided adequately address the dispute?\n"
            "3. Should the Issuer accept, or proceed to pre-arbitration/arbitration?\n"
            "4. Are there any procedural issues with the response?",
            context=summary,
        )

        return TaskResult(
            success=True,
            decision="RESPONSE_EVALUATED",
            reasoning=analysis,
            data={"response_data": response_data, "analysis": analysis},
            next_actions=[TaskType.PREPARE_PRE_ARBITRATION],
        )

    async def _prepare_pre_arbitration(self, dispute: Dispute, task: DisputeTask) -> TaskResult:
        """Prepare a pre-arbitration attempt or response."""
        rule = get_condition_rule(dispute.condition)

        if dispute.uses_dispute_response_flow:
            # For Cat 12/13: Issuer files pre-arb after Dispute Response
            actor = "Issuer"
            options = [
                "Provide new documentation or information about the Dispute",
                "Change the Dispute condition (if original was valid + new condition met)",
                "Certify that cardholder still disputes the transaction",
            ]
        else:
            # For Cat 10/11: Acquirer files pre-arb after Dispute
            actor = "Acquirer"
            options = [pa.evidence_types for pa in rule.pre_arbitration_rights]
            options = [item for sublist in options for item in sublist]

        summary = self._format_dispute_summary(dispute)
        analysis = await self._reason(
            f"Prepare a pre-arbitration {'attempt' if actor == 'Acquirer' else 'response'} for this dispute.\n"
            f"Available options for {actor}:\n" + "\n".join(f"  - {o}" for o in options) +
            "\n\nDetermine the strongest approach and what evidence to include.",
            context=summary,
        )

        return TaskResult(
            success=True,
            decision="PRE_ARB_PREPARED",
            reasoning=analysis,
            data={"actor": actor, "options": options, "analysis": analysis},
            next_actions=[TaskType.EVALUATE_PRE_ARBITRATION],
        )

    async def _evaluate_pre_arbitration(self, dispute: Dispute, task: DisputeTask) -> TaskResult:
        """Evaluate pre-arbitration outcome and determine next steps."""
        summary = self._format_dispute_summary(dispute)

        analysis = await self._reason(
            "Evaluate the pre-arbitration cycle for this dispute and determine:\n"
            "1. Has the dispute been resolved?\n"
            "2. Should it proceed to Arbitration? (10 calendar days to file)\n"
            "3. Is a Compliance filing more appropriate?\n"
            "4. What is the likely outcome if it goes to Arbitration?",
            context=summary,
        )

        return TaskResult(
            success=True,
            decision="PRE_ARB_EVALUATED",
            reasoning=analysis,
            data={"analysis": analysis},
            next_actions=[TaskType.PREPARE_ARBITRATION],
        )
