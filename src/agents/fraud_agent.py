"""Fraud dispute processing agent (Category 10).

Handles all fraud-related disputes including:
- 10.1: EMV Liability Shift Counterfeit Fraud
- 10.2: EMV Liability Shift Non-Counterfeit Fraud
- 10.3: Other Fraud - Card-Present Environment
- 10.4: Other Fraud - Card-Absent Environment
- 10.5: Visa Fraud Monitoring Program
"""

from src.agents.base_agent import BaseDisputeAgent
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)
from src.rules.documentation import (
    check_documentation_requirements,
    check_fraud_type_code_requirement,
)
from src.rules.time_limits import is_within_time_limit
from src.rules.validity import check_dispute_validity, convert_to_rule_evaluation


class FraudDisputeAgent(BaseDisputeAgent):
    """Agent specializing in Category 10 (Fraud) dispute processing.

    Implements the full processing logic for fraud disputes as specified
    in Visa Core Rules Section 11.7, including:
    - Validity checking per condition
    - Time limit verification
    - Documentation requirement validation
    - Fraud type code verification
    - Decision rendering with rule citations
    """

    def __init__(self) -> None:
        super().__init__(AgentType.FRAUD)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate that this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.FRAUD

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a fraud dispute through the full evaluation pipeline.

        Pipeline:
        1. Verify time limit compliance
        2. Check dispute validity (invalid dispute conditions)
        3. Validate documentation requirements
        4. Verify fraud type code reporting
        5. Render decision
        """
        self.logger.info(
            "Processing fraud dispute: case=%s condition=%s", case.case_id, case.condition
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(DisputeLifecycleStage.RULE_EVALUATION, "Fraud agent evaluating rules")

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
                rule_section="11.7.x.4",
                rule_description=f"Dispute time limit for condition {case.condition.value}",
                is_satisfied=within_limit,
                details="Within time limit" if within_limit else "EXCEEDED time limit",
            )
            all_evaluations.append(time_eval)
            case.add_rule_evaluation(time_eval)
            case.is_within_time_limit = within_limit

            if not within_limit:
                case.add_processing_note("Dispute filed outside time limit - REJECTED")
                case.advance_stage(DisputeLifecycleStage.DECISION, "Time limit exceeded")
                case.decision = self.create_decision(
                    resolution=DisputeResolution.INVALID_DISPUTE,
                    rationale="Dispute filed outside the allowed time limit per Section 11.7",
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
            case.add_processing_note(f"Dispute invalid: {reasons}")
            case.advance_stage(DisputeLifecycleStage.DECISION, "Invalid dispute detected")
            case.decision = self.create_decision(
                resolution=DisputeResolution.INVALID_DISPUTE,
                rationale=f"Dispute is invalid per Visa Rules: {reasons}",
                rule_evaluations=all_evaluations,
                confidence=0.95,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Rejected: invalid dispute")
            return case

        # Step 3: Documentation check
        doc_result = check_documentation_requirements(case)
        doc_eval = RuleEvaluationResult(
            rule_id="documentation_check",
            rule_section="11.7.x.5",
            rule_description="Documentation requirements for fraud dispute",
            is_satisfied=doc_result.is_complete,
            details=doc_result.details,
        )
        all_evaluations.append(doc_eval)
        case.add_rule_evaluation(doc_eval)

        # Step 4: Fraud type code check
        fraud_code_result = check_fraud_type_code_requirement(case)
        fraud_eval = RuleEvaluationResult(
            rule_id="fraud_type_code_check",
            rule_section="11.7.x.2",
            rule_description="Fraud type code reporting requirement",
            is_satisfied=fraud_code_result.is_complete,
            details=fraud_code_result.details,
        )
        all_evaluations.append(fraud_eval)
        case.add_rule_evaluation(fraud_eval)

        # Step 5: Render decision
        case.advance_stage(DisputeLifecycleStage.DECISION, "Rendering decision")

        if not doc_result.is_complete or not fraud_code_result.is_complete:
            # Missing requirements - escalate or request more info
            missing = doc_result.missing_requirements + fraud_code_result.missing_requirements
            confidence = 0.60
            needs_human = True
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    f"Fraud dispute requires additional documentation: {missing}. "
                    "Provisional decision pending human review."
                ),
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=needs_human,
                human_review_reason=f"Missing documentation: {missing}",
            )
        else:
            # All requirements met - issuer wins the fraud dispute
            confidence = 0.90
            needs_human = self._should_escalate_to_human(confidence, case)
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    f"Fraud dispute validated under condition {case.condition.value if case.condition else 'unknown'}. "
                    "All validity checks passed, documentation complete, fraud type code reported. "
                    "Issuer's dispute is upheld per Section 11.7."
                ),
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=needs_human,
                human_review_reason="High-value dispute" if needs_human else None,
            )

        if case.decision.requires_human_review:
            case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to human review")
        else:
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Decision rendered")

        self.logger.info(
            "Fraud dispute processed: case=%s resolution=%s confidence=%.2f",
            case.case_id,
            case.decision.resolution.value,
            case.decision.confidence_score,
        )
        return case
