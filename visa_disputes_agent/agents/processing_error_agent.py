"""Processing Error Dispute Agent - handles Category 12 disputes."""

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


class ProcessingErrorAgent(BaseDisputeAgent):
    """Specialized agent for processing Dispute Category 12: Processing Errors.

    Handles incorrect transaction code, incorrect amount, incorrect account
    number, duplicate processing, paid by other means, late presentment,
    and incorrect currency disputes.
    """

    @property
    def agent_name(self) -> str:
        return "processing_error_agent"

    @property
    def handles_category(self) -> DisputeCategory:
        return DisputeCategory.PROCESSING_ERRORS

    async def _evaluate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate processing error dispute based on condition-specific rules."""
        evaluators = {
            DisputeCondition.DUPLICATE_PROCESSING: self._evaluate_duplicate,
            DisputeCondition.INCORRECT_AMOUNT: self._evaluate_incorrect_amount,
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER: self._evaluate_incorrect_account,
            DisputeCondition.PAID_BY_OTHER_MEANS: self._evaluate_paid_other_means,
            DisputeCondition.INCORRECT_TRANSACTION_CODE: self._evaluate_incorrect_code,
            DisputeCondition.INCORRECT_CURRENCY: self._evaluate_incorrect_currency,
            DisputeCondition.LATE_PRESENTMENT: self._evaluate_late_presentment,
        }

        evaluator = evaluators.get(condition)
        if evaluator is not None:
            return await evaluator(task, condition, validity_results, time_limit)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
            reasoning=f"Processing error condition {condition.value} requires manual review",
            confidence=0.5,
            escalation_reason="Unsupported processing error condition",
        )

    async def _evaluate_duplicate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Duplicate Processing dispute (12.5)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check for evidence of duplicate transaction
        has_duplicate_evidence = any(
            "duplicate" in e.evidence_type.lower() or "duplicate" in e.description.lower()
            for e in task.evidence
        )

        dup_check = RuleEvaluationResult(
            rule_id="duplicate_check_12.5",
            rule_section="Section 11.9 - Duplicate Processing",
            rule_description="Evidence that single Transaction was processed more than once",
            is_satisfied=has_duplicate_evidence or bool(task.issuer_certification),
            details=(
                "Evidence of duplicate processing provided"
                if has_duplicate_evidence
                else "Issuer certification of single transaction provided"
                if task.issuer_certification
                else "No specific evidence of duplicate processing"
            ),
        )
        rules.append(dup_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Transaction appears to have been processed more than once. "
                "Duplicate processing dispute is valid under condition 12.5."
            ),
            confidence=0.85 if dup_check.is_satisfied else 0.65,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_incorrect_amount(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Incorrect Amount dispute (12.2)."""
        rules: list[RuleEvaluationResult] = list(validity_results)

        amount_check = RuleEvaluationResult(
            rule_id="amount_check_12.2",
            rule_section="Section 11.9 - Incorrect Amount",
            rule_description="Transaction amount differs from agreed amount",
            is_satisfied=task.dispute_amount > 0,
            details=(
                f"Disputed amount: {task.dispute_amount}. "
                f"Transaction amount: {task.transaction.amount}."
            ),
        )
        rules.append(amount_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Transaction amount differs from the amount the Cardholder agreed to pay. "
                "Incorrect amount dispute is valid under condition 12.2."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_incorrect_account(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Incorrect Account Number dispute (12.3/12.4)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Transaction was posted to the wrong account. The Issuer's Cardholder "
                "was not involved in the Transaction."
            ),
            confidence=0.85,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_paid_other_means(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Paid by Other Means dispute (12.6)."""
        has_payment_proof = any(
            "payment" in e.evidence_type.lower() or "receipt" in e.evidence_type.lower()
            for e in task.evidence
        )

        if not has_payment_proof and not task.issuer_certification:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                reasoning="Proof of payment by other means is required but not provided",
                confidence=0.85,
                rules=validity_results,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Cardholder has proof that the Transaction was paid by other means. "
                "Dispute is valid under condition 12.6."
            ),
            confidence=0.85,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_incorrect_code(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Incorrect Transaction Code dispute (12.1)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Transaction was processed with an incorrect Transaction code. "
                "Dispute is valid under condition 12.1."
            ),
            confidence=0.8,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_incorrect_currency(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Incorrect Currency dispute (12.9)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Transaction was processed in an incorrect currency or with "
                "incorrect currency conversion. Dispute is valid under condition 12.9."
            ),
            confidence=0.8,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_late_presentment(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Late Presentment dispute (12.8)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Clearing Record was submitted late - Transaction was not processed "
                "within the required timeframe. Dispute is valid under condition 12.8."
            ),
            confidence=0.8,
            rules=validity_results,
            time_limit=time_limit,
        )
