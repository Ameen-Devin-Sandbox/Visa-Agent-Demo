"""Base class for dispute processing sub-agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

import structlog

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
    DisputeWorkflowState,
)
from visa_disputes_agent.rules.engine import RulesEngine
from visa_disputes_agent.workflow.state_machine import DisputeWorkflow

logger = structlog.get_logger()


class BaseDisputeAgent(ABC):
    """Abstract base class for specialized dispute processing agents.

    Each sub-agent handles a specific dispute category and knows how to
    evaluate disputes according to the applicable Visa rules.
    """

    def __init__(self, rules_engine: RulesEngine) -> None:
        self._rules = rules_engine
        self._log = logger.bind(agent=self.agent_name)

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Unique name for this agent."""
        ...

    @property
    @abstractmethod
    def handles_category(self) -> DisputeCategory:
        """The dispute category this agent handles."""
        ...

    async def process(self, task: DisputeTask) -> DisputeDecision:
        """Process a dispute task through the full workflow.

        This is the main entry point called by the orchestrator.
        """
        self._log.info("processing_started", task_id=str(task.task_id))
        task.assigned_agent = self.agent_name
        workflow = DisputeWorkflow(task)

        try:
            # Step 1: Validation
            workflow.transition_to(DisputeWorkflowState.VALIDATION)
            validation_result = await self._validate(task)
            if not validation_result.is_satisfied:
                return self._create_decision(
                    task,
                    outcome=DecisionOutcome.DISPUTE_INVALID,
                    reasoning=f"Validation failed: {validation_result.details}",
                    confidence=0.95,
                    rules=[validation_result],
                )

            # Step 2: Categorization
            workflow.transition_to(DisputeWorkflowState.CATEGORIZATION)
            condition = await self._categorize(task)
            if condition is None:
                return self._create_decision(
                    task,
                    outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
                    reasoning="Unable to determine dispute condition automatically",
                    confidence=0.3,
                    escalation_reason="Classification failed",
                )
            task.dispute_condition = condition
            task.add_log_entry("categorized", f"Classified as condition {condition.value}")

            # Step 3: Rule Evaluation (check for invalid dispute)
            workflow.transition_to(DisputeWorkflowState.RULE_EVALUATION)
            validity_results = self._rules.check_dispute_validity(task, condition)
            invalid_matches = [r for r in validity_results if r.is_satisfied]
            if invalid_matches:
                return self._create_decision(
                    task,
                    outcome=DecisionOutcome.DISPUTE_INVALID,
                    reasoning=(
                        "Dispute is invalid due to: "
                        + "; ".join(r.details for r in invalid_matches)
                    ),
                    confidence=0.95,
                    rules=validity_results,
                )

            # Step 4: Evidence Review
            workflow.transition_to(DisputeWorkflowState.EVIDENCE_REVIEW)
            doc_result = self._rules.evaluate_documentation_completeness(task, condition)
            if not doc_result.is_satisfied:
                return self._create_decision(
                    task,
                    outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                    reasoning=f"Documentation incomplete: {doc_result.details}",
                    confidence=0.85,
                    rules=[doc_result],
                )

            # Step 5: Time Limit Check
            workflow.transition_to(DisputeWorkflowState.TIME_LIMIT_CHECK)
            time_result = self._rules.check_time_limits(task, condition)
            if time_result is not None and not time_result.is_within_time_limit:
                return self._create_decision(
                    task,
                    outcome=DecisionOutcome.DISPUTE_INVALID,
                    reasoning=(
                        f"Dispute filed outside time limit. Deadline was "
                        f"{time_result.deadline_date}, filed on "
                        f"{task.dispute_filing_date}"
                    ),
                    confidence=0.99,
                    rules=validity_results,
                    time_limit=time_result,
                )

            # Step 6: Category-specific evaluation
            workflow.transition_to(DisputeWorkflowState.DECISION)
            decision = await self._evaluate(task, condition, validity_results, time_result)

            # Step 7: Generate response
            if decision.is_final():
                workflow.transition_to(DisputeWorkflowState.RESPONSE_GENERATION)
                decision = await self._generate_response(task, condition, decision)
                workflow.transition_to(DisputeWorkflowState.RESOLUTION)
            elif decision.outcome == DecisionOutcome.ESCALATE_TO_PRE_ARBITRATION:
                workflow.transition_to(DisputeWorkflowState.PRE_ARBITRATION)
            elif decision.outcome == DecisionOutcome.ESCALATE_TO_HUMAN:
                workflow.transition_to(DisputeWorkflowState.ESCALATED_TO_HUMAN)

            self._log.info(
                "processing_completed",
                task_id=str(task.task_id),
                outcome=decision.outcome.value,
                confidence=decision.confidence_score,
            )
            return decision

        except Exception as e:
            self._log.error(
                "processing_error",
                task_id=str(task.task_id),
                error=str(e),
                exc_info=True,
            )
            return self._create_decision(
                task,
                outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
                reasoning=f"Processing error: {str(e)}",
                confidence=0.0,
                escalation_reason=f"Unexpected error: {str(e)}",
            )

    async def _validate(self, task: DisputeTask) -> RuleEvaluationResult:
        """Validate basic dispute requirements (Section 1.10.1.1)."""
        issues: list[str] = []

        # Check: Issuer must attempt to honor the Transaction first
        if not task.cardholder.attempted_merchant_resolution:
            # This is a requirement for some conditions, not all
            pass

        # Check: Cardholder must have suffered financial loss
        if (
            not task.cardholder.financial_loss_confirmed
            and task.dispute_category != DisputeCategory.AUTHORIZATION
        ):
            issues.append("Cardholder financial loss not confirmed")

        # Check: Dispute amount must be positive
        if task.dispute_amount <= 0:
            issues.append("Dispute amount must be greater than zero")

        # Check: Transaction data is present
        if not task.transaction.transaction_id:
            issues.append("Transaction ID is required")

        is_valid = len(issues) == 0
        return RuleEvaluationResult(
            rule_id="basic_validation",
            rule_section="Section 1.10.1.1 - Attempt to Settle",
            rule_description="Basic dispute validation requirements",
            is_satisfied=is_valid,
            details="Validation passed" if is_valid else f"Validation issues: {'; '.join(issues)}",
        )

    async def _categorize(self, task: DisputeTask) -> DisputeCondition | None:
        """Categorize the dispute into a specific condition."""
        return self._rules.classify_dispute(task)

    @abstractmethod
    async def _evaluate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Perform category-specific dispute evaluation.

        This is where each sub-agent applies its specialized logic.
        """
        ...

    async def _generate_response(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        decision: DisputeDecision,
    ) -> DisputeDecision:
        """Generate the response details for the decision."""
        response_reqs = self._rules.get_response_requirements(condition)
        if response_reqs:
            decision.required_actions = [
                item
                for req in response_reqs
                for item in req.required_evidence
            ]
        return decision

    def _create_decision(
        self,
        task: DisputeTask,
        outcome: DecisionOutcome,
        reasoning: str,
        confidence: float,
        rules: list[RuleEvaluationResult] | None = None,
        time_limit: TimeLimitResult | None = None,
        escalation_reason: str = "",
    ) -> DisputeDecision:
        """Helper to create a DisputeDecision."""
        return DisputeDecision(
            task_id=task.task_id,
            outcome=outcome,
            confidence_score=confidence,
            dispute_amount_approved=(
                task.dispute_amount
                if outcome == DecisionOutcome.DISPUTE_VALID
                else Decimal("0")
            ),
            reasoning=reasoning,
            applicable_rules=rules or [],
            time_limit_check=time_limit,
            escalation_reason=escalation_reason,
        )
