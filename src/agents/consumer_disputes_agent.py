"""Consumer disputes processing agent (Category 13).

Handles consumer dispute conditions:
- 13.1: Merchandise/Services Not Received
- 13.2: Cancelled Recurring Transaction
- 13.3: Not as Described or Defective Merchandise/Services
- 13.4: Counterfeit Merchandise
- 13.5: Misrepresentation
- 13.6: Credit Not Processed
- 13.7: Cancelled Merchandise/Services
- 13.8: Original Credit Transaction Not Accepted
- 13.9: Non-Receipt of Cash at an ATM
"""

from src.agents.base_agent import BaseDisputeAgent
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeCondition,
    DisputeLifecycleStage,
    DisputeResolution,
    TransactionEnvironment,
)
from src.rules.documentation import check_documentation_requirements
from src.rules.time_limits import is_within_time_limit
from src.rules.validity import check_dispute_validity, convert_to_rule_evaluation


class ConsumerDisputesAgent(BaseDisputeAgent):
    """Agent specializing in Category 13 (Consumer Disputes) processing.

    Consumer disputes follow the Category 12/13 flow (Section 11.2.3)
    which includes a Dispute Response stage before Pre-Arbitration.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.CONSUMER_DISPUTES)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.CONSUMER_DISPUTES

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a consumer dispute.

        Pipeline:
        1. Time limit verification
        2. Validity checks
        3. Consumer-dispute-specific validation
        4. Documentation check
        5. Decision rendering
        """
        self.logger.info(
            "Processing consumer dispute: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(
            DisputeLifecycleStage.RULE_EVALUATION,
            "Consumer disputes agent evaluating",
        )

        all_evaluations: list[RuleEvaluationResult] = []

        # Step 1: Time limit check
        if case.condition and case.dispute_filed_date:
            within_limit = is_within_time_limit(
                event_date=case.transaction.processing_date,
                filing_date=case.dispute_filed_date,
                condition=case.condition,
                region=case.transaction.region,
            )
            time_eval = RuleEvaluationResult(
                rule_id="time_limit_check",
                rule_section="11.10.x.4",
                rule_description=f"Time limit for condition {case.condition.value}",
                is_satisfied=within_limit,
                details="Within time limit" if within_limit else "EXCEEDED time limit",
            )
            all_evaluations.append(time_eval)
            case.add_rule_evaluation(time_eval)
            case.is_within_time_limit = within_limit

            if not within_limit:
                case.add_processing_note("Consumer dispute filed outside time limit")
                case.advance_stage(DisputeLifecycleStage.DECISION, "Time limit exceeded")
                case.decision = self.create_decision(
                    resolution=DisputeResolution.INVALID_DISPUTE,
                    rationale="Dispute filed outside the allowed time limit per Section 11.10",
                    rule_evaluations=all_evaluations,
                    confidence=0.99,
                )
                case.advance_stage(DisputeLifecycleStage.RESOLVED, "Rejected: time limit exceeded")
                return case

        # Step 2: Validity checks
        validity_results = check_dispute_validity(case)
        for result in validity_results:
            eval_result = convert_to_rule_evaluation(result)
            all_evaluations.append(eval_result)
            case.add_rule_evaluation(eval_result)

        invalid_results = [r for r in validity_results if not r.is_valid]
        if invalid_results:
            reasons = "; ".join(r.reason for r in invalid_results)
            case.add_processing_note(f"Consumer dispute invalid: {reasons}")
            case.advance_stage(DisputeLifecycleStage.DECISION, "Invalid dispute")
            case.decision = self.create_decision(
                resolution=DisputeResolution.INVALID_DISPUTE,
                rationale=f"Consumer dispute invalid: {reasons}",
                rule_evaluations=all_evaluations,
                confidence=0.95,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Rejected: invalid dispute")
            return case

        # Step 3: Consumer-dispute-specific validation
        consumer_eval = self._validate_consumer_specifics(case)
        all_evaluations.append(consumer_eval)
        case.add_rule_evaluation(consumer_eval)

        # Step 4: Documentation check
        doc_result = check_documentation_requirements(case)
        doc_eval = RuleEvaluationResult(
            rule_id="documentation_check",
            rule_section="11.10.x.5",
            rule_description="Documentation requirements for consumer dispute",
            is_satisfied=doc_result.is_complete,
            details=doc_result.details,
        )
        all_evaluations.append(doc_eval)
        case.add_rule_evaluation(doc_eval)

        # Step 5: Decision
        case.advance_stage(DisputeLifecycleStage.DECISION, "Rendering decision")

        if not consumer_eval.is_satisfied:
            confidence = 0.80
            case.decision = self.create_decision(
                resolution=DisputeResolution.ACQUIRER_WIN,
                rationale=f"Consumer dispute claim not substantiated: {consumer_eval.details}",
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=self._should_escalate_to_human(confidence, case),
            )
        elif not doc_result.is_complete:
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    "Consumer dispute conditions met but documentation incomplete. "
                    f"Missing: {doc_result.missing_requirements}"
                ),
                rule_evaluations=all_evaluations,
                confidence=0.65,
                requires_human_review=True,
                human_review_reason=f"Missing documentation: {doc_result.missing_requirements}",
            )
        else:
            confidence = 0.88
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    f"Consumer dispute validated under condition {case.condition.value if case.condition else 'unknown'}. "
                    "Requirements met and documentation provided. "
                    "Issuer's dispute upheld per Section 11.10."
                ),
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=self._should_escalate_to_human(confidence, case),
            )

        if case.decision.requires_human_review:
            case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to human review")
        else:
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Decision rendered")

        return case

    def _validate_consumer_specifics(self, case: DisputeCase) -> RuleEvaluationResult:
        """Validate consumer-dispute-specific conditions."""
        txn = case.transaction

        if case.condition == DisputeCondition.MERCHANDISE_NOT_RECEIVED:
            return RuleEvaluationResult(
                rule_id="consumer_merch_not_received",
                rule_section="11.10.2",
                rule_description="Cardholder claims merchandise/services not received",
                is_satisfied=True,
                details="Cardholder statement supports merchandise/services not received claim",
            )

        if case.condition == DisputeCondition.CANCELLED_RECURRING:
            if not txn.is_recurring:
                return RuleEvaluationResult(
                    rule_id="consumer_cancelled_recurring",
                    rule_section="11.10.3",
                    rule_description="Transaction must be a recurring transaction",
                    is_satisfied=False,
                    details="Transaction is not flagged as recurring",
                )
            return RuleEvaluationResult(
                rule_id="consumer_cancelled_recurring",
                rule_section="11.10.3",
                rule_description="Recurring transaction billed after cancellation",
                is_satisfied=True,
                details="Recurring transaction confirmed, cancellation claimed",
            )

        if case.condition == DisputeCondition.NOT_AS_DESCRIBED:
            has_description = any(
                "description" in e.evidence_type.lower() or "defective" in e.description.lower()
                for e in case.evidence
            )
            return RuleEvaluationResult(
                rule_id="consumer_not_as_described",
                rule_section="11.10.4",
                rule_description="Merchandise/services not as described or defective",
                is_satisfied=has_description or bool(case.cardholder.cardholder_statement),
                details="Description discrepancy evidence provided"
                if has_description
                else "Cardholder statement provided",
            )

        if case.condition == DisputeCondition.COUNTERFEIT_MERCHANDISE:
            has_counterfeit_evidence = any(
                "counterfeit" in e.evidence_type.lower() or "counterfeit" in e.description.lower()
                for e in case.evidence
            )
            return RuleEvaluationResult(
                rule_id="consumer_counterfeit",
                rule_section="11.10.5",
                rule_description="Merchandise is counterfeit",
                is_satisfied=has_counterfeit_evidence,
                details=(
                    "Counterfeit evidence provided"
                    if has_counterfeit_evidence
                    else "No counterfeit evidence provided"
                ),
            )

        if case.condition == DisputeCondition.CREDIT_NOT_PROCESSED:
            has_credit_claim = len(case.prior_credits) > 0 or any(
                "credit" in e.description.lower() or "refund" in e.description.lower()
                for e in case.evidence
            )
            return RuleEvaluationResult(
                rule_id="consumer_credit_not_processed",
                rule_section="11.10.7",
                rule_description="Expected credit was not processed",
                is_satisfied=has_credit_claim,
                details=(
                    "Credit/refund evidence provided"
                    if has_credit_claim
                    else "No evidence of expected credit"
                ),
            )

        if case.condition == DisputeCondition.NON_RECEIPT_CASH_ATM:
            is_atm = txn.environment == TransactionEnvironment.ATM
            return RuleEvaluationResult(
                rule_id="consumer_atm_no_cash",
                rule_section="11.10.10",
                rule_description="Cash not received at ATM",
                is_satisfied=is_atm,
                details="ATM transaction confirmed" if is_atm else "Not an ATM transaction",
            )

        # Default: accept with cardholder statement
        return RuleEvaluationResult(
            rule_id="consumer_generic_check",
            rule_section="11.10",
            rule_description="Consumer dispute validation",
            is_satisfied=bool(case.cardholder.cardholder_statement),
            details=(
                "Cardholder statement provided"
                if case.cardholder.cardholder_statement
                else "No cardholder statement"
            ),
        )
