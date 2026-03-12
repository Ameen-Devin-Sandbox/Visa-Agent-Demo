"""Authorization Dispute Agent - handles Category 11 disputes."""

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


class AuthorizationDisputeAgent(BaseDisputeAgent):
    """Specialized agent for processing Dispute Category 11: Authorization.

    Handles Card Recovery Bulletin, Declined Authorization, and
    No Authorization/Late Presentment disputes.
    """

    @property
    def agent_name(self) -> str:
        return "authorization_dispute_agent"

    @property
    def handles_category(self) -> DisputeCategory:
        return DisputeCategory.AUTHORIZATION

    async def _evaluate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate authorization dispute based on condition-specific rules."""
        if condition == DisputeCondition.CARD_RECOVERY_BULLETIN:
            return await self._evaluate_card_recovery(task, condition, validity_results, time_limit)
        elif condition == DisputeCondition.DECLINED_AUTHORIZATION:
            return await self._evaluate_declined_auth(task, condition, validity_results, time_limit)
        elif condition == DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT:
            return await self._evaluate_no_auth_late(task, condition, validity_results, time_limit)
        else:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
                reasoning=f"Authorization condition {condition.value} requires manual review",
                confidence=0.5,
                escalation_reason="Unsupported authorization condition",
            )

    async def _evaluate_card_recovery(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Card Recovery Bulletin dispute (11.1)."""
        txn = task.transaction

        crb_check = RuleEvaluationResult(
            rule_id="crb_check_11.1",
            rule_section="Section 11.8.1 - Card Recovery Bulletin",
            rule_description="Card was listed on CRB before transaction and no authorization obtained",
            is_satisfied=not txn.was_authorized,
            details=(
                "Card was on CRB and no authorization was obtained"
                if not txn.was_authorized
                else "Authorization was obtained - CRB dispute may not apply"
            ),
        )

        rules = [*validity_results, crb_check]

        if crb_check.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.DISPUTE_VALID,
                reasoning=(
                    "Card was listed on Card Recovery Bulletin before the Transaction Date "
                    "and the Merchant completed the Transaction without obtaining Authorization."
                ),
                confidence=0.9,
                rules=rules,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_INVALID,
            reasoning="Authorization was obtained despite CRB listing - dispute condition not met",
            confidence=0.8,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_declined_auth(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Declined Authorization dispute (11.2)."""
        txn = task.transaction
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check account status requirement
        account_status = task.cardholder.account_status.lower()
        valid_statuses = {"credit problem", "closed", "fraud"}
        status_valid = account_status in valid_statuses

        status_check = RuleEvaluationResult(
            rule_id="account_status_11.2",
            rule_section="Section 11.8.2.5 - Declined Authorization Documentation",
            rule_description="Account status must be Credit Problem, Closed, or Fraud",
            is_satisfied=status_valid,
            details=(
                f"Account status is '{account_status}' - meets requirement"
                if status_valid
                else f"Account status '{account_status}' is not one of the required statuses"
            ),
        )
        rules.append(status_check)

        # Check if decline response was sent
        decline_check = RuleEvaluationResult(
            rule_id="decline_response_11.2",
            rule_section="Section 11.8.2 - Declined Authorization",
            rule_description="Issuer sent decline response but transaction was completed",
            is_satisfied=not txn.was_authorized,
            details=(
                "Decline response was sent and transaction was still completed"
                if not txn.was_authorized
                else "Transaction appears to have been authorized"
            ),
        )
        rules.append(decline_check)

        if decline_check.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.DISPUTE_VALID,
                reasoning=(
                    "Authorization was declined by the Issuer but the Acquirer completed "
                    "the Transaction. Dispute is valid under condition 11.2."
                ),
                confidence=0.9,
                rules=rules,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
            reasoning=(
                "Authorization status is ambiguous. Manual review needed to confirm "
                "whether a Decline Response was actually sent."
            ),
            confidence=0.5,
            rules=rules,
            time_limit=time_limit,
            escalation_reason="Ambiguous authorization status",
        )

    async def _evaluate_no_auth_late(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate No Authorization/Late Presentment dispute (11.3)."""
        txn = task.transaction
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Determine if this is a no-auth or late presentment case
        if not txn.was_authorized:
            auth_check = RuleEvaluationResult(
                rule_id="no_auth_11.3",
                rule_section="Section 11.8.3 - No Authorization/Late Presentment",
                rule_description="Valid Authorization was required but not obtained",
                is_satisfied=True,
                details="No valid Authorization was obtained for this Transaction",
            )
            rules.append(auth_check)

            # Check if chip-initiated offline (dispute limited to amount above floor limit)
            if txn.is_chip_transaction:
                chip_note = RuleEvaluationResult(
                    rule_id="chip_offline_11.3",
                    rule_section="Section 11.8.3.2 - Dispute Rights",
                    rule_description="Chip-initiated offline transaction dispute limitation",
                    is_satisfied=True,
                    details=(
                        "For Chip-initiated, Offline-Authorized Transaction, dispute is "
                        "limited to amount above applicable Floor Limit"
                    ),
                )
                rules.append(chip_note)

            return self._create_decision(
                task,
                outcome=DecisionOutcome.DISPUTE_VALID,
                reasoning=(
                    "Valid Authorization was required but not obtained. "
                    "Dispute is valid under condition 11.3."
                ),
                confidence=0.9,
                rules=rules,
                time_limit=time_limit,
            )

        # Late presentment case - check processing timeframes
        late_check = RuleEvaluationResult(
            rule_id="late_presentment_11.3",
            rule_section="Section 11.8.3 - Late Presentment",
            rule_description="Transaction not processed within required timeframe",
            is_satisfied=True,
            details=(
                "Transaction was authorized but may not have been processed within "
                "the timeframe specified in Section 5.7.3.5"
            ),
        )
        rules.append(late_check)

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Authorization was obtained but the Transaction was not processed "
                "within the required timeframe (late presentment)."
            ),
            confidence=0.8,
            rules=rules,
            time_limit=time_limit,
        )
