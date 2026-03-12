"""Authorization dispute processing agent (Category 11).

Handles authorization-related disputes:
- 11.1: Card Recovery Bulletin
- 11.2: Declined Authorization
- 11.3: No Authorization / Late Presentment
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


class AuthorizationDisputeAgent(BaseDisputeAgent):
    """Agent specializing in Category 11 (Authorization) dispute processing.

    Implements processing logic for authorization disputes per Section 11.8:
    - 11.1: Card listed on CRB at time of transaction
    - 11.2: Authorization was declined but transaction was completed
    - 11.3: No valid authorization obtained or late presentment
    """

    def __init__(self) -> None:
        super().__init__(AgentType.AUTHORIZATION)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.AUTHORIZATION

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process an authorization dispute.

        Pipeline:
        1. Time limit verification
        2. Validity checks
        3. Authorization-specific validation
        4. Documentation check
        5. Decision rendering
        """
        self.logger.info(
            "Processing authorization dispute: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(DisputeLifecycleStage.RULE_EVALUATION, "Authorization agent evaluating")

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
                rule_section="11.8.x.4",
                rule_description=f"Dispute time limit for condition {case.condition.value}",
                is_satisfied=within_limit,
                details="Within time limit" if within_limit else "EXCEEDED time limit",
            )
            all_evaluations.append(time_eval)
            case.add_rule_evaluation(time_eval)
            case.is_within_time_limit = within_limit

            if not within_limit:
                case.add_processing_note("Authorization dispute filed outside time limit")
                case.advance_stage(DisputeLifecycleStage.DECISION, "Time limit exceeded")
                case.decision = self.create_decision(
                    resolution=DisputeResolution.INVALID_DISPUTE,
                    rationale="Dispute filed outside the allowed time limit per Section 11.8",
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
            case.add_processing_note(f"Authorization dispute invalid: {reasons}")
            case.advance_stage(DisputeLifecycleStage.DECISION, "Invalid dispute")
            case.decision = self.create_decision(
                resolution=DisputeResolution.INVALID_DISPUTE,
                rationale=f"Authorization dispute invalid: {reasons}",
                rule_evaluations=all_evaluations,
                confidence=0.95,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Rejected: invalid dispute")
            return case

        # Step 3: Authorization-specific validation
        auth_eval = self._validate_authorization_specifics(case)
        all_evaluations.append(auth_eval)
        case.add_rule_evaluation(auth_eval)

        # Step 4: Documentation check
        doc_result = check_documentation_requirements(case)
        doc_eval = RuleEvaluationResult(
            rule_id="documentation_check",
            rule_section="11.8.x.5",
            rule_description="Documentation requirements for authorization dispute",
            is_satisfied=doc_result.is_complete,
            details=doc_result.details,
        )
        all_evaluations.append(doc_eval)
        case.add_rule_evaluation(doc_eval)

        # Step 5: Decision
        case.advance_stage(DisputeLifecycleStage.DECISION, "Rendering decision")

        if not auth_eval.is_satisfied:
            confidence = 0.85
            case.decision = self.create_decision(
                resolution=DisputeResolution.ACQUIRER_WIN,
                rationale=(
                    f"Authorization dispute does not meet requirements: {auth_eval.details}. "
                    "Acquirer is not liable."
                ),
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=self._should_escalate_to_human(confidence, case),
            )
        elif not doc_result.is_complete:
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    "Authorization dispute conditions met but documentation incomplete. "
                    f"Missing: {doc_result.missing_requirements}"
                ),
                rule_evaluations=all_evaluations,
                confidence=0.65,
                requires_human_review=True,
                human_review_reason=f"Missing documentation: {doc_result.missing_requirements}",
            )
        else:
            confidence = 0.90
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale=(
                    f"Authorization dispute validated under condition {case.condition.value if case.condition else 'unknown'}. "
                    "Authorization requirements were not met by the acquirer. "
                    "Issuer's dispute is upheld per Section 11.8."
                ),
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=self._should_escalate_to_human(confidence, case),
            )

        if case.decision.requires_human_review:
            case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to human review")
        else:
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Decision rendered")

        self.logger.info(
            "Authorization dispute processed: case=%s resolution=%s",
            case.case_id,
            case.decision.resolution.value,
        )
        return case

    def _validate_authorization_specifics(self, case: DisputeCase) -> RuleEvaluationResult:
        """Validate authorization-specific conditions."""
        txn = case.transaction

        if case.condition == DisputeCondition.CARD_RECOVERY_BULLETIN:
            # 11.1: Must prove card was on CRB at time of transaction
            has_crb_evidence = any(
                "crb" in e.evidence_type.lower() or "card recovery" in e.description.lower()
                for e in case.evidence
            )
            return RuleEvaluationResult(
                rule_id="auth_crb_check",
                rule_section="11.8.1",
                rule_description="Card must be listed on Card Recovery Bulletin",
                is_satisfied=has_crb_evidence,
                details="CRB listing evidence provided"
                if has_crb_evidence
                else "No CRB listing evidence",
            )

        if case.condition == DisputeCondition.DECLINED_AUTHORIZATION:
            # 11.2: Authorization response must show decline
            is_declined = (
                txn.authorization_response_code is not None
                and not txn.authorization_response_code.startswith("0")
            )
            return RuleEvaluationResult(
                rule_id="auth_declined_check",
                rule_section="11.8.2",
                rule_description="Authorization must have been declined",
                is_satisfied=is_declined,
                details=(
                    f"Authorization declined (code: {txn.authorization_response_code})"
                    if is_declined
                    else "Authorization was not declined"
                ),
            )

        if case.condition == DisputeCondition.NO_AUTHORIZATION:
            # 11.3: No valid authorization code
            no_auth = txn.authorization_code is None
            return RuleEvaluationResult(
                rule_id="auth_no_auth_check",
                rule_section="11.8.3",
                rule_description="No valid authorization was obtained",
                is_satisfied=no_auth,
                details="No authorization code found" if no_auth else "Authorization code exists",
            )

        return RuleEvaluationResult(
            rule_id="auth_generic_check",
            rule_section="11.8",
            rule_description="Generic authorization check",
            is_satisfied=True,
            details="No specific authorization validation required",
        )
