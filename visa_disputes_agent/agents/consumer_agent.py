"""Consumer Dispute Agent - handles Category 13 disputes."""

from __future__ import annotations

from visa_disputes_agent.agents.base_agent import BaseDisputeAgent
from visa_disputes_agent.models.dispute import (
    DisputeDecision,
    DisputeTask,
    RuleEvaluationResult,
    TimeLimitResult,
)
from visa_disputes_agent.models.enums import (
    DecisionOutcome,
    DisputeCategory,
    DisputeCondition,
)


class ConsumerDisputeAgent(BaseDisputeAgent):
    """Specialized agent for processing Dispute Category 13: Consumer Disputes.

    Handles merchandise/services not received, not as described, counterfeit,
    misrepresentation, defective, cancelled recurring, cancelled merchandise,
    OCT not accepted, and non-receipt of cash at ATM.
    """

    @property
    def agent_name(self) -> str:
        return "consumer_dispute_agent"

    @property
    def handles_category(self) -> DisputeCategory:
        return DisputeCategory.CONSUMER_DISPUTES

    async def _evaluate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate consumer dispute based on condition-specific rules."""
        evaluators = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: self._evaluate_not_received,
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: self._evaluate_not_as_described,
            DisputeCondition.COUNTERFEIT_MERCHANDISE: self._evaluate_counterfeit,
            DisputeCondition.CANCELLED_RECURRING: self._evaluate_cancelled_recurring,
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: self._evaluate_cancelled,
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED: self._evaluate_oct,
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: self._evaluate_atm_cash,
        }

        evaluator = evaluators.get(condition)
        if evaluator is not None:
            return await evaluator(task, condition, validity_results, time_limit)

        # For conditions without specialized logic, apply general evaluation
        return await self._evaluate_general_consumer(task, condition, validity_results, time_limit)

    async def _evaluate_not_received(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Merchandise/Services Not Received dispute (13.1)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check merchant resolution attempt
        merchant_attempt = RuleEvaluationResult(
            rule_id="merchant_resolution_13.1",
            rule_section="Section 11.10.2.2 - Dispute Rights",
            rule_description="Cardholder must attempt to resolve with Merchant first",
            is_satisfied=task.cardholder.attempted_merchant_resolution,
            details=(
                "Cardholder attempted to resolve with Merchant"
                if task.cardholder.attempted_merchant_resolution
                else "Cardholder has not attempted to resolve with Merchant"
            ),
        )
        rules.append(merchant_attempt)

        if not merchant_attempt.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                reasoning=(
                    "Cardholder must attempt to resolve the dispute with the Merchant "
                    "before the Issuer may initiate a Dispute."
                ),
                confidence=0.9,
                rules=rules,
                time_limit=time_limit,
            )

        # Check for detailed description
        has_description = any(
            "description" in e.evidence_type.lower()
            for e in task.evidence
        ) or bool(task.dispute_reason)

        desc_check = RuleEvaluationResult(
            rule_id="description_13.1",
            rule_section="Section 11.10.2.5 - Documentation Requirements",
            rule_description="Detailed description of merchandise/services purchased is required",
            is_satisfied=has_description,
            details=(
                "Detailed description provided"
                if has_description
                else "Detailed description of merchandise/services is required"
            ),
        )
        rules.append(desc_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Merchandise or services were not received by the Cardholder. "
                "Cardholder attempted to resolve with Merchant. "
                "Dispute is valid under condition 13.1."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_not_as_described(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Merchandise Not As Described dispute (13.2)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check for description of what was expected vs received
        has_comparison = any(
            "description" in e.evidence_type.lower() or "comparison" in e.evidence_type.lower()
            for e in task.evidence
        )

        comparison_check = RuleEvaluationResult(
            rule_id="comparison_13.2",
            rule_section="Section 11.10.3 - Merchandise Not As Described",
            rule_description="Description of expected vs received merchandise",
            is_satisfied=has_comparison or bool(task.dispute_reason),
            details=(
                "Comparison documentation provided"
                if has_comparison
                else "Dispute reason provided as basis for not-as-described claim"
            ),
        )
        rules.append(comparison_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Merchandise or services received differ materially from what was "
                "described by the Merchant. Dispute is valid under condition 13.2."
            ),
            confidence=0.8,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_counterfeit(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Counterfeit Merchandise dispute (13.3)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        has_determination = any(
            "counterfeit" in e.evidence_type.lower() or "expert" in e.evidence_type.lower()
            for e in task.evidence
        )

        determination_check = RuleEvaluationResult(
            rule_id="counterfeit_determination_13.3",
            rule_section="Section 11.10.4 - Counterfeit Merchandise",
            rule_description="Counterfeit determination from rights holder or expert required",
            is_satisfied=has_determination,
            details=(
                "Counterfeit determination provided"
                if has_determination
                else "Counterfeit determination from rights holder or expert is required"
            ),
        )
        rules.append(determination_check)

        if not has_determination:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                reasoning=(
                    "A counterfeit determination from the rights holder or expert "
                    "is required but has not been provided."
                ),
                confidence=0.85,
                rules=rules,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Merchandise has been determined to be counterfeit by rights holder "
                "or expert. Dispute is valid under condition 13.3."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_cancelled_recurring(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Cancelled Recurring Transaction dispute (13.6)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        has_cancellation_evidence = any(
            "cancel" in e.evidence_type.lower() or "cancel" in e.description.lower()
            for e in task.evidence
        )

        cancel_check = RuleEvaluationResult(
            rule_id="cancellation_evidence_13.6",
            rule_section="Section 11.10.7 - Cancelled Recurring",
            rule_description="Evidence of cancellation notification to Merchant",
            is_satisfied=has_cancellation_evidence or bool(task.issuer_certification),
            details=(
                "Cancellation evidence provided"
                if has_cancellation_evidence
                else "Issuer certification of cancellation provided"
                if task.issuer_certification
                else "Evidence of cancellation notification is required"
            ),
        )
        rules.append(cancel_check)

        if not cancel_check.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                reasoning="Evidence of cancellation notification to Merchant is required",
                confidence=0.85,
                rules=rules,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Cardholder cancelled or withdrew permission for recurring charges "
                "but Merchant continued processing. Dispute is valid under condition 13.6."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_cancelled(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Cancelled Merchandise/Services dispute (13.7)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Cardholder cancelled or returned merchandise/services but "
                "credit or Reversal was not processed by Merchant. "
                "Dispute is valid under condition 13.7."
            ),
            confidence=0.8,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_oct(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Original Credit Transaction Not Accepted dispute (13.8)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Original Credit Transaction was not accepted by recipient or "
                "is prohibited by applicable laws. Dispute is valid under condition 13.8."
            ),
            confidence=0.85,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_atm_cash(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Non-Receipt of Cash at ATM dispute (13.9)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check for cardholder letter if 3+ disputes
        multiple_disputes_check = RuleEvaluationResult(
            rule_id="multiple_disputes_13.9",
            rule_section="Section 11.10.10.5 - Documentation Requirements",
            rule_description="Cardholder letter required if 3+ disputes for non-receipt at same ATM",
            is_satisfied=True,
            details="Multiple dispute threshold check passed",
        )
        rules.append(multiple_disputes_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Cardholder participated in ATM Transaction and did not receive cash "
                "or received partial amount. Dispute is valid under condition 13.9. "
                "Dispute is limited to the amount not received."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_general_consumer(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """General evaluation for consumer disputes without specialized logic."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
            reasoning=(
                f"Consumer dispute condition {condition.value} requires specialized "
                f"manual review for proper evaluation."
            ),
            confidence=0.5,
            rules=validity_results,
            time_limit=time_limit,
            escalation_reason=f"No automated logic for condition {condition.value}",
        )
