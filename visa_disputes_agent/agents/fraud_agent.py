"""Fraud Dispute Agent - handles Category 10 disputes."""

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


class FraudDisputeAgent(BaseDisputeAgent):
    """Specialized agent for processing Dispute Category 10: Fraud.

    Handles EMV liability shift (counterfeit and non-counterfeit),
    card-present fraud, card-absent fraud, and Visa fraud monitoring
    program disputes.
    """

    @property
    def agent_name(self) -> str:
        return "fraud_dispute_agent"

    @property
    def handles_category(self) -> DisputeCategory:
        return DisputeCategory.FRAUD

    async def _evaluate(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate fraud dispute based on condition-specific rules."""
        if condition == DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT:
            return await self._evaluate_emv_counterfeit(task, condition, validity_results, time_limit)
        elif condition == DisputeCondition.EMV_LIABILITY_SHIFT_NON_COUNTERFEIT:
            return await self._evaluate_emv_non_counterfeit(task, condition, validity_results, time_limit)
        elif condition == DisputeCondition.OTHER_FRAUD_CARD_PRESENT:
            return await self._evaluate_card_present_fraud(task, condition, validity_results, time_limit)
        elif condition == DisputeCondition.OTHER_FRAUD_CARD_ABSENT:
            return await self._evaluate_card_absent_fraud(task, condition, validity_results, time_limit)
        else:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
                reasoning=f"Fraud condition {condition.value} requires manual review",
                confidence=0.5,
                escalation_reason="Unsupported fraud condition for automated processing",
            )

    async def _evaluate_emv_counterfeit(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate EMV Liability Shift Counterfeit Fraud (10.1)."""
        txn = task.transaction
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check EMV liability shift conditions
        emv_check = RuleEvaluationResult(
            rule_id="emv_liability_shift_10.1",
            rule_section="Section 11.7.2 - EMV Liability Shift Counterfeit Fraud",
            rule_description="EMV liability shift qualification check",
            is_satisfied=True,
            details="",
        )

        if not task.cardholder.is_chip_card:
            emv_check.is_satisfied = False
            emv_check.details = "Card is not a Chip Card - EMV liability shift does not apply"
        elif txn.is_chip_reading_device and txn.has_full_chip_data:
            emv_check.is_satisfied = False
            emv_check.details = (
                "Transaction was at Chip-Reading Device with Full-Chip Data - "
                "liability shift does not apply to Acquirer"
            )
        else:
            emv_check.details = (
                "EMV liability shift applies: Card is Chip Card and "
                "transaction did not meet chip processing requirements"
            )

        rules.append(emv_check)

        if not emv_check.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.DISPUTE_INVALID,
                reasoning=emv_check.details,
                confidence=0.9,
                rules=rules,
                time_limit=time_limit,
            )

        # Check for compelling evidence from acquirer
        compelling_evidence = self._check_compelling_evidence(task, condition)
        if compelling_evidence.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.REQUIRES_COMPELLING_EVIDENCE,
                reasoning="Acquirer has provided compelling evidence that may invalidate dispute",
                confidence=0.7,
                rules=[*rules, compelling_evidence],
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "EMV liability shift applies. Transaction was completed with counterfeit "
                "card and chip processing requirements were not met by acquirer."
            ),
            confidence=0.9,
            rules=rules,
            time_limit=time_limit,
        )

    async def _evaluate_emv_non_counterfeit(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate EMV Liability Shift Non-Counterfeit Fraud (10.2)."""
        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "EMV liability shift applies for non-counterfeit fraud "
                "(lost/stolen/not received item). Cardholder denies authorization."
            ),
            confidence=0.85,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_card_present_fraud(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Other Fraud - Card Present (10.3)."""
        # Check if cardholder has provided denial
        has_denial = task.has_cardholder_letter or bool(task.issuer_certification)

        if not has_denial:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.INSUFFICIENT_DOCUMENTATION,
                reasoning="Cardholder letter or Issuer certification denying authorization is required",
                confidence=0.85,
                rules=validity_results,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Card-present fraud dispute is valid. Cardholder denies "
                "authorization and required documentation has been provided."
            ),
            confidence=0.85,
            rules=validity_results,
            time_limit=time_limit,
        )

    async def _evaluate_card_absent_fraud(
        self,
        task: DisputeTask,
        condition: DisputeCondition,
        validity_results: list[RuleEvaluationResult],
        time_limit: TimeLimitResult | None,
    ) -> DisputeDecision:
        """Evaluate Other Fraud - Card Absent (10.4)."""
        txn = task.transaction
        rules: list[RuleEvaluationResult] = list(validity_results)

        # Check Visa Secure authentication
        if txn.is_visa_secure:
            visa_secure_check = RuleEvaluationResult(
                rule_id="visa_secure_check_10.4",
                rule_section="Section 11.7 - Visa Secure Liability Shift",
                rule_description="Visa Secure authentication shifts liability to issuer",
                is_satisfied=True,
                details=(
                    "Transaction was authenticated via Visa Secure. "
                    "Liability shifts to Issuer for authenticated transactions."
                ),
            )
            rules.append(visa_secure_check)
            return self._create_decision(
                task,
                outcome=DecisionOutcome.DISPUTE_INVALID,
                reasoning=(
                    "Dispute is invalid: Transaction was authenticated via Visa Secure. "
                    "Liability shifts to Issuer for Visa Secure authenticated transactions."
                ),
                confidence=0.95,
                rules=rules,
                time_limit=time_limit,
            )

        # Check compelling evidence (CE 3.0 - matching data points)
        compelling_evidence = self._check_compelling_evidence(task, condition)
        rules.append(compelling_evidence)

        if compelling_evidence.is_satisfied:
            return self._create_decision(
                task,
                outcome=DecisionOutcome.REQUIRES_COMPELLING_EVIDENCE,
                reasoning=(
                    "Acquirer has provided compelling evidence matching data points "
                    "from undisputed transactions."
                ),
                confidence=0.75,
                rules=rules,
                time_limit=time_limit,
            )

        return self._create_decision(
            task,
            outcome=DecisionOutcome.DISPUTE_VALID,
            reasoning=(
                "Card-absent fraud dispute is valid. Cardholder denies authorization, "
                "transaction was not Visa Secure authenticated, and no compelling "
                "evidence has been provided."
            ),
            confidence=0.85,
            rules=rules,
            time_limit=time_limit,
        )

    def _check_compelling_evidence(
        self, task: DisputeTask, condition: DisputeCondition
    ) -> RuleEvaluationResult:
        """Check if compelling evidence has been provided by the acquirer."""
        ce_items = self._rules.get_compelling_evidence_items(condition)
        matching_evidence = [
            e for e in task.evidence
            if e.is_compelling
        ]

        if matching_evidence:
            return RuleEvaluationResult(
                rule_id=f"compelling_evidence_{condition.value}",
                rule_section="Section 11.5.2 - Use of Compelling Evidence",
                rule_description="Compelling evidence evaluation",
                is_satisfied=True,
                details=f"Found {len(matching_evidence)} compelling evidence item(s)",
                evidence_provided=[e.description for e in matching_evidence],
            )

        return RuleEvaluationResult(
            rule_id=f"compelling_evidence_{condition.value}",
            rule_section="Section 11.5.2 - Use of Compelling Evidence",
            rule_description="Compelling evidence evaluation",
            is_satisfied=False,
            details="No compelling evidence provided by acquirer",
            evidence_required=[item.description for item in ce_items[:5]],
        )
