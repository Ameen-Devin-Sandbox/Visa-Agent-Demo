"""Pre-arbitration and arbitration processing agent.

Handles the escalation stages of dispute resolution:
- Pre-arbitration attempts (acquirer response to dispute)
- Pre-arbitration responses (issuer response to pre-arbitration)
- Arbitration filing evaluation
"""

from src.agents.base_agent import BaseDisputeAgent
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)
from src.rules.compelling_evidence import (
    convert_to_rule_evaluation as ce_to_eval,
)
from src.rules.compelling_evidence import (
    evaluate_compelling_evidence,
)


class PreArbitrationAgent(BaseDisputeAgent):
    """Agent handling pre-arbitration and arbitration stages.

    Per Section 11.2.2 (Categories 10/11):
    - Dispute -> Pre-Arbitration Attempt (30 days) -> Pre-Arb Response (30 days) -> Arbitration (10 days)

    Per Section 11.2.3 (Categories 12/13):
    - Dispute -> Dispute Response (30 days) -> Pre-Arb Attempt (30 days) -> Pre-Arb Response (30 days) -> Arbitration (10 days)
    """

    def __init__(self) -> None:
        super().__init__(AgentType.PRE_ARBITRATION)

    async def validate(self, case: DisputeCase) -> bool:
        """This agent handles cases in pre-arbitration or arbitration stages."""
        return case.stage in (
            DisputeLifecycleStage.PRE_ARBITRATION,
            DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
            DisputeLifecycleStage.ARBITRATION,
        )

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a pre-arbitration or arbitration action.

        Evaluates:
        1. Whether compelling evidence has been provided
        2. Whether the pre-arbitration/arbitration is timely
        3. Whether escalation to arbitration is warranted
        """
        self.logger.info(
            "Processing pre-arbitration: case=%s stage=%s",
            case.case_id,
            case.stage.value,
        )
        case.assigned_agent = self.agent_type.value

        all_evaluations: list[RuleEvaluationResult] = []

        if case.stage == DisputeLifecycleStage.PRE_ARBITRATION:
            return await self._process_pre_arbitration(case, all_evaluations)
        elif case.stage == DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE:
            return await self._process_pre_arbitration_response(case, all_evaluations)
        elif case.stage == DisputeLifecycleStage.ARBITRATION:
            return await self._process_arbitration(case, all_evaluations)

        return case

    async def _process_pre_arbitration(
        self,
        case: DisputeCase,
        evaluations: list[RuleEvaluationResult],
    ) -> DisputeCase:
        """Process a pre-arbitration attempt by the acquirer.

        The acquirer may provide:
        - Evidence that a credit/reversal was not addressed
        - Evidence that the dispute is invalid
        - Evidence that the cardholder no longer disputes
        - Compelling Evidence (for certain conditions)
        """
        case.pre_arbitration_attempts += 1
        case.add_processing_note(
            f"Pre-arbitration attempt #{case.pre_arbitration_attempts} being evaluated"
        )

        # Evaluate compelling evidence from acquirer
        acquirer_evidence = [e for e in case.evidence if e.provided_by == "acquirer"]
        ce_results = evaluate_compelling_evidence(case, acquirer_evidence)

        has_compelling = False
        for ce_result in ce_results:
            eval_result = ce_to_eval(ce_result)
            evaluations.append(eval_result)
            case.add_rule_evaluation(eval_result)
            if ce_result.is_compelling:
                has_compelling = True

        # Check for other valid pre-arbitration grounds
        has_credit_not_addressed = any(
            "credit" in e.description.lower() and "not addressed" in e.description.lower()
            for e in acquirer_evidence
        )
        has_invalid_evidence = any("invalid" in e.description.lower() for e in acquirer_evidence)
        has_cardholder_withdrew = any(
            "no longer disputes" in e.description.lower() or "withdrew" in e.description.lower()
            for e in acquirer_evidence
        )

        pre_arb_eval = RuleEvaluationResult(
            rule_id="pre_arb_evaluation",
            rule_section="11.2.2"
            if case.category in (DisputeCategory.FRAUD, DisputeCategory.AUTHORIZATION)
            else "11.2.3",
            rule_description="Pre-arbitration attempt evaluation",
            is_satisfied=has_compelling
            or has_credit_not_addressed
            or has_invalid_evidence
            or has_cardholder_withdrew,
            details=self._build_pre_arb_details(
                has_compelling,
                has_credit_not_addressed,
                has_invalid_evidence,
                has_cardholder_withdrew,
            ),
        )
        evaluations.append(pre_arb_eval)
        case.add_rule_evaluation(pre_arb_eval)

        # Determine outcome
        if has_compelling:
            case.add_processing_note("Compelling evidence provided - issuer must evaluate")
            case.advance_stage(
                DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
                "Compelling evidence received; awaiting issuer response",
            )
        elif has_cardholder_withdrew:
            case.decision = self.create_decision(
                resolution=DisputeResolution.WITHDRAWN,
                rationale="Cardholder no longer disputes the transaction",
                rule_evaluations=evaluations,
                confidence=0.90,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Dispute withdrawn by cardholder")
        elif has_credit_not_addressed or has_invalid_evidence:
            case.advance_stage(
                DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
                "Pre-arbitration evidence provided; awaiting issuer response",
            )
        else:
            case.add_processing_note("No valid pre-arbitration grounds provided")
            case.decision = self.create_decision(
                resolution=DisputeResolution.ISSUER_WIN,
                rationale="Pre-arbitration attempt lacks valid grounds; original dispute upheld",
                rule_evaluations=evaluations,
                confidence=0.85,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Pre-arbitration rejected")

        return case

    async def _process_pre_arbitration_response(
        self,
        case: DisputeCase,
        evaluations: list[RuleEvaluationResult],
    ) -> DisputeCase:
        """Process the issuer's response to a pre-arbitration attempt.

        Per Section 11.2.2: The issuer may:
        - Accept financial responsibility
        - Decline the pre-arbitration if compelling evidence was provided
          and the issuer certifies the cardholder's info doesn't match or
          the cardholder still disputes after reviewing evidence
        - Provide new documentation
        """
        case.add_processing_note("Evaluating pre-arbitration response")

        # Check if issuer accepted responsibility
        issuer_evidence = [e for e in case.evidence if e.provided_by == "issuer"]
        accepted_responsibility = any(
            "accept" in e.description.lower() and "responsib" in e.description.lower()
            for e in issuer_evidence
        )

        if accepted_responsibility:
            case.decision = self.create_decision(
                resolution=DisputeResolution.ACQUIRER_WIN,
                rationale="Issuer accepted financial responsibility in pre-arbitration response",
                rule_evaluations=evaluations,
                confidence=0.95,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Issuer accepted responsibility")
            return case

        # Check if issuer declined with valid certification
        has_certification = case.issuer_certification is not None
        has_new_documentation = any(e.submitted_at > case.created_at for e in issuer_evidence)

        if has_certification or has_new_documentation:
            case.add_processing_note(
                "Issuer declined pre-arbitration with certification/new docs - may proceed to arbitration"
            )
            # This would normally go to the acquirer for potential arbitration filing
            case.decision = self.create_decision(
                resolution=DisputeResolution.ESCALATED_ARBITRATION,
                rationale=(
                    "Pre-arbitration cycle complete. Issuer has declined with "
                    f"{'certification' if has_certification else 'new documentation'}. "
                    "Acquirer may file for Arbitration within 10 calendar days."
                ),
                rule_evaluations=evaluations,
                confidence=0.80,
                requires_human_review=True,
                human_review_reason="Arbitration filing decision required",
            )
            case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Arbitration decision pending")
        else:
            # Issuer did not respond adequately
            case.decision = self.create_decision(
                resolution=DisputeResolution.ACQUIRER_WIN,
                rationale="Issuer failed to provide adequate pre-arbitration response",
                rule_evaluations=evaluations,
                confidence=0.85,
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Issuer response inadequate")

        return case

    async def _process_arbitration(
        self,
        case: DisputeCase,
        evaluations: list[RuleEvaluationResult],
    ) -> DisputeCase:
        """Process an arbitration filing.

        Per Section 11.11: Arbitration is the final stage when:
        - The Dispute and Pre-Arbitration cycle has been completed
        - The opposing party has not met Visa Rules requirements
        """
        case.arbitration_filed = True
        case.add_processing_note("Arbitration case filed - escalating to Visa committee")

        arb_eval = RuleEvaluationResult(
            rule_id="arbitration_filing",
            rule_section="11.11",
            rule_description="Arbitration filing evaluation",
            is_satisfied=True,
            details="Arbitration filed after pre-arbitration cycle completion",
        )
        evaluations.append(arb_eval)
        case.add_rule_evaluation(arb_eval)

        # Arbitration decisions are made by Visa's committee - always escalate to human
        case.decision = self.create_decision(
            resolution=DisputeResolution.ESCALATED_ARBITRATION,
            rationale=(
                "Case escalated to Arbitration per Section 11.11. "
                "The Visa Arbitration Committee will review and render a binding decision. "
                "Required documentation per Section 11.11.1 must be submitted."
            ),
            rule_evaluations=evaluations,
            confidence=0.70,
            requires_human_review=True,
            human_review_reason="Arbitration requires Visa committee review",
        )
        case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to Visa arbitration")

        return case

    def _build_pre_arb_details(
        self,
        has_compelling: bool,
        has_credit_not_addressed: bool,
        has_invalid_evidence: bool,
        has_cardholder_withdrew: bool,
    ) -> str:
        """Build a detailed description of pre-arbitration evaluation."""
        parts: list[str] = []
        if has_compelling:
            parts.append("Compelling evidence provided by acquirer")
        if has_credit_not_addressed:
            parts.append("Credit/reversal not addressed in dispute")
        if has_invalid_evidence:
            parts.append("Evidence that dispute is invalid")
        if has_cardholder_withdrew:
            parts.append("Cardholder no longer disputes the transaction")
        if not parts:
            parts.append("No valid pre-arbitration grounds identified")
        return "; ".join(parts)
