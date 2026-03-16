"""AI-powered authorization dispute processing agent (Category 11).

Uses OpenAI to reason over Visa Core Rules Section 11.8 to evaluate
authorization disputes and render decisions.

Handles authorization-related disputes:
- 11.1: Card Recovery Bulletin
- 11.2: Declined Authorization
- 11.3: No Authorization / Late Presentment
"""

from src.agents.base_agent import BaseDisputeAgent
from src.llm.visa_rules import get_authorization_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)

_AUTH_SYSTEM_PROMPT = """\
You are a specialized Visa authorization dispute processing agent. You evaluate \
authorization disputes (Category 11) according to Visa Core Rules Section 11.8.

Your evaluation must consider:
1. Whether the dispute is valid (check for invalid dispute conditions per Section 11.8)
2. Whether time limits have been met
3. Whether required documentation has been provided
4. Authorization-specific validation:
   - 11.1 (Card Recovery Bulletin): Was the card on the CRB at time of transaction?
   - 11.2 (Declined Authorization): Was authorization actually declined?
   - 11.3 (No Authorization): Was no valid authorization obtained?
5. The strength of the authorization claim based on available evidence

You MUST respond with valid JSON in this exact format:
{
    "is_valid": true/false,
    "validity_reason": "<explanation of validity determination>",
    "resolution": "<one of: issuer_win, acquirer_win, invalid_dispute>",
    "confidence": <float 0.0-1.0>,
    "rationale": "<detailed explanation citing specific Visa rules sections>",
    "rule_citations": [
        {
            "rule_section": "<e.g. 11.8.1>",
            "rule_description": "<what the rule says>",
            "is_satisfied": true/false,
            "details": "<how this rule applies to this case>"
        }
    ],
    "requires_human_review": true/false,
    "human_review_reason": "<reason if human review needed, null otherwise>"
}
"""


class AuthorizationDisputeAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 11 (Authorization) disputes.

    Uses OpenAI to reason over Visa Core Rules Section 11.8 to evaluate
    authorization disputes, check validity, and render decisions.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.AUTHORIZATION)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.AUTHORIZATION

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process an authorization dispute using AI reasoning over Visa rules."""
        self.logger.info(
            "Processing authorization dispute via AI: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(
            DisputeLifecycleStage.RULE_EVALUATION,
            "AI authorization agent evaluating",
        )

        rules_context = get_authorization_rules()
        result = self._evaluate_dispute_with_llm(case, rules_context, _AUTH_SYSTEM_PROMPT)

        all_evaluations: list[RuleEvaluationResult] = []
        for citation in result.get("rule_citations", []):
            eval_result = RuleEvaluationResult(
                rule_id=f"ai_auth_{citation['rule_section'].replace('.', '_')}",
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

        self.logger.info(
            "AI authorization dispute processed: case=%s resolution=%s",
            case.case_id,
            case.decision.resolution.value,
        )
        return case
