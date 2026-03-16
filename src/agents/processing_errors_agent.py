"""Processing errors dispute agent (Category 12).

Handles processing error disputes:
- 12.2: Incorrect Transaction Code
- 12.3: Incorrect Currency
- 12.4: Incorrect Account Number
- 12.5: Incorrect Amount
- 12.6: Duplicate Processing / Paid by Other Means
- 12.7: Invalid Data
"""

from src.agents.base_agent import BaseDisputeAgent
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeCondition,
    DisputeLifecycleStage,
    DisputeResolution,
)
from src.rules.documentation import check_documentation_requirements
from src.rules.time_limits import is_within_time_limit
from src.rules.validity import check_dispute_validity, convert_to_rule_evaluation


class ProcessingErrorsAgent(BaseDisputeAgent):
    """Agent specializing in Category 12 (Processing Errors) disputes.

    Processing errors follow the Category 12/13 dispute resolution flow
    (Section 11.2.3) which includes a Dispute Response stage before
    Pre-Arbitration.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.PROCESSING_ERRORS)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.PROCESSING_ERRORS

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a processing error dispute.

        Pipeline:
        1. Time limit verification
        2. Validity checks
        3. Processing-error-specific validation
        4. Documentation check
        5. Decision rendering
        """
        self.logger.info(
            "Processing errors dispute: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(
            DisputeLifecycleStage.RULE_EVALUATION,
            "Processing errors agent evaluating",
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
                rule_section="11.9.x.4",
                rule_description=f"Time limit for condition {case.condition.value}",
                is_satisfied=within_limit,
                details="Within time limit" if within_limit else "EXCEEDED time limit",
            )
            all_evaluations.append(time_eval)
            case.add_rule_evaluation(time_eval)
            case.is_within_time_limit = within_limit

            if not within_limit:
                case.add_processing_note("Processing error dispute filed outside time limit")
                case.advance_stage(DisputeLifecycleStage.DECISION, "Time limit exceeded")
                case.decision = self.create_decision(
                    resolution=DisputeResolution.INVALID_DISPUTE,
                    rationale="Dispute filed outside the allowed time limit per Section 11.9",
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
            case.add_processing_note(f"Processing error dispute invalid: {reasons}")
            case.advance_stage(DisputeLifecycleStage.DECISION, "Invalid dispute")
            case.decision = self.create_decision(
                resolution=DisputeResolution.INVALID_DISPUTE,
                rationale=f"Processing error dispute invalid: {reasons}",
                rule_evaluations=all_evaluations,
                confidence=0.95,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Rejected: invalid dispute")
            return case

        # Step 3: Processing-error-specific validation
        error_eval = self._validate_processing_error(case)
        all_evaluations.append(error_eval)
        case.add_rule_evaluation(error_eval)

        # Step 4: Documentation check
        doc_result = check_documentation_requirements(case)
        doc_eval = RuleEvaluationResult(
            rule_id="documentation_check",
            rule_section="11.9.x.5",
            rule_description="Documentation requirements for processing error dispute",
            is_satisfied=doc_result.is_complete,
            details=doc_result.details,
        )
        all_evaluations.append(doc_eval)
        case.add_rule_evaluation(doc_eval)

        # Step 5: Decision
        case.advance_stage(DisputeLifecycleStage.DECISION, "Rendering decision")

        if not error_eval.is_satisfied:
            confidence = 0.80
            case.decision = self.create_decision(
                resolution=DisputeResolution.ACQUIRER_WIN,
                rationale=f"Processing error claim not substantiated: {error_eval.details}",
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=self._should_escalate_to_human(confidence, case),
            )
        elif not doc_result.is_complete:
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    "Processing error conditions met but documentation incomplete. "
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
                    f"Processing error dispute validated under condition {case.condition.value if case.condition else 'unknown'}. "
                    "Error confirmed and documentation provided. "
                    "Issuer's dispute upheld per Section 11.9."
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

    def _validate_processing_error(self, case: DisputeCase) -> RuleEvaluationResult:
        """Validate processing-error-specific conditions."""
        txn = case.transaction

        if case.condition == DisputeCondition.INCORRECT_AMOUNT:
            has_amount_evidence = (
                case.dispute_amount is not None and case.dispute_amount != txn.amount
            )
            return RuleEvaluationResult(
                rule_id="proc_incorrect_amount",
                rule_section="11.9.4",
                rule_description="Transaction amount differs from agreed amount",
                is_satisfied=has_amount_evidence,
                details=(
                    f"Disputed amount: {case.dispute_amount}, Transaction amount: {txn.amount}"
                    if has_amount_evidence
                    else "No amount discrepancy demonstrated"
                ),
            )

        if case.condition == DisputeCondition.INCORRECT_CURRENCY:
            has_currency_evidence = (
                case.dispute_currency is not None and case.dispute_currency != txn.currency
            )
            return RuleEvaluationResult(
                rule_id="proc_incorrect_currency",
                rule_section="11.9.2",
                rule_description="Transaction currency differs from expected currency",
                is_satisfied=has_currency_evidence,
                details=(
                    f"Disputed currency: {case.dispute_currency}, Transaction currency: {txn.currency}"
                    if has_currency_evidence
                    else "No currency discrepancy demonstrated"
                ),
            )

        if case.condition == DisputeCondition.DUPLICATE_PROCESSING:
            has_duplicate_evidence = any(
                "duplicate" in e.evidence_type.lower() or "duplicate" in e.description.lower()
                for e in case.evidence
            )
            return RuleEvaluationResult(
                rule_id="proc_duplicate",
                rule_section="11.9.5",
                rule_description="Transaction was processed more than once",
                is_satisfied=has_duplicate_evidence,
                details=(
                    "Duplicate processing evidence provided"
                    if has_duplicate_evidence
                    else "No duplicate processing evidence"
                ),
            )

        # Default: evidence-based check
        has_evidence = len(case.evidence) > 0
        return RuleEvaluationResult(
            rule_id="proc_generic_check",
            rule_section="11.9",
            rule_description="Processing error evidence check",
            is_satisfied=has_evidence,
            details="Evidence provided" if has_evidence else "No evidence provided",
        )
