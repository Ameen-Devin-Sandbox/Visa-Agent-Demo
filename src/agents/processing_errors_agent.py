"""AI-powered processing errors dispute agent (Category 12).

Uses OpenAI to reason over Visa Core Rules Section 11.9 to evaluate
processing error disputes and render decisions.

Handles processing error disputes:
- 12.2: Incorrect Transaction Code
- 12.3: Incorrect Currency
- 12.4: Incorrect Account Number
- 12.5: Incorrect Amount
- 12.6: Duplicate Processing / Paid by Other Means
- 12.7: Invalid Data
"""

from src.agents.base_agent import BaseDisputeAgent
from src.llm.visa_rules import get_processing_errors_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)

_PROC_ERRORS_SYSTEM_PROMPT = """\
You are a specialized Visa processing errors dispute agent. You evaluate \
processing error disputes (Category 12) according to Visa Core Rules Section 11.9.

Your evaluation must consider:
1. Whether the dispute is valid (check for invalid dispute conditions per Section 11.9)
2. Whether time limits have been met
3. Whether required documentation has been provided
4. Processing-error-specific validation:
   - 12.2 (Incorrect Transaction Code): Was the wrong transaction code used?
   - 12.3 (Incorrect Currency): Was the transaction processed in the wrong currency?
   - 12.4 (Incorrect Account Number): Was the transaction posted to the wrong account?
   - 12.5 (Incorrect Amount): Does the amount differ from what was agreed?
   - 12.6 (Duplicate Processing): Was the transaction processed more than once?
   - 12.7 (Invalid Data): Does the transaction contain invalid data?
5. The strength of the processing error claim based on available evidence

You MUST respond with valid JSON in this exact format:
{
    "is_valid": true/false,
    "validity_reason": "<explanation of validity determination>",
    "resolution": "<one of: issuer_win, acquirer_win, invalid_dispute>",
    "confidence": <float 0.0-1.0>,
    "rationale": "<detailed explanation citing specific Visa rules sections>",
    "rule_citations": [
        {
            "rule_section": "<e.g. 11.9.5>",
            "rule_description": "<what the rule says>",
            "is_satisfied": true/false,
            "details": "<how this rule applies to this case>"
        }
    ],
    "requires_human_review": true/false,
    "human_review_reason": "<reason if human review needed, null otherwise>"
}
"""


class ProcessingErrorsAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 12 (Processing Errors) disputes.

    Uses OpenAI to reason over Visa Core Rules Section 11.9 to evaluate
    processing error disputes, check validity, and render decisions.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.PROCESSING_ERRORS)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.PROCESSING_ERRORS

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a processing error dispute using AI reasoning over Visa rules."""
        self.logger.info(
            "Processing errors dispute via AI: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(
            DisputeLifecycleStage.RULE_EVALUATION,
            "AI processing errors agent evaluating",
        )

        rules_context = get_processing_errors_rules()
        result = self._evaluate_dispute_with_llm(
            case, rules_context, _PROC_ERRORS_SYSTEM_PROMPT
        )

        all_evaluations: list[RuleEvaluationResult] = []
        for citation in result.get("rule_citations", []):
            eval_result = RuleEvaluationResult(
                rule_id=f"ai_proc_{citation['rule_section'].replace('.', '_')}",
                rule_section=citation["rule_section"],
                rule_description=citation["rule_description"],
                is_satisfied=citation["is_satisfied"],
                details=citation["details"],
            )
            all_evaluations.append(eval_result)
            case.add_rule_evaluation(eval_result)

        case.advance_stage(DisputeLifecycleStage.DECISION, "AI rendering decision")

        if not result.get("is_valid", True):
            case.add_processing_note(
                f"AI determined dispute invalid: {result.get('validity_reason', 'Unknown')}"
            )
            case.decision = self.create_decision(
                resolution=DisputeResolution.INVALID_DISPUTE,
                rationale=f"[AI] {result['rationale']}",
                rule_evaluations=all_evaluations,
                confidence=float(result.get("confidence", 0.90)),
            )
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "AI rejected: invalid dispute")
            return case

        resolution_str = result.get("resolution", "issuer_win")
        resolution = DisputeResolution(resolution_str)
        confidence = float(result.get("confidence", 0.85))
        requires_human = result.get("requires_human_review", False)
        human_reason = result.get("human_review_reason")

        if self._should_escalate_to_human(confidence, case):
            requires_human = True
            human_reason = human_reason or "Low confidence or high-value dispute"

        case.decision = self.create_decision(
            resolution=resolution,
            rationale=f"[AI] {result['rationale']}",
            rule_evaluations=all_evaluations,
            confidence=confidence,
            requires_human_review=requires_human,
            human_review_reason=human_reason,
        )

        if case.decision.requires_human_review:
            case.advance_stage(DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to human review")
        else:
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "AI decision rendered")

        return case
