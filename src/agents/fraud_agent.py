"""AI-powered fraud dispute processing agent (Category 10).

Uses OpenAI to reason over Visa Core Rules Section 11.7 to evaluate
fraud disputes and render decisions.

Handles all fraud-related disputes including:
- 10.1: EMV Liability Shift Counterfeit Fraud
- 10.2: EMV Liability Shift Non-Counterfeit Fraud
- 10.3: Other Fraud - Card-Present Environment
- 10.4: Other Fraud - Card-Absent Environment
- 10.5: Visa Fraud Monitoring Program
"""

from src.agents.base_agent import BaseDisputeAgent
from src.llm.visa_rules import get_fraud_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)

_FRAUD_SYSTEM_PROMPT = """\
You are a specialized Visa fraud dispute processing agent. You evaluate fraud \
disputes (Category 10) according to Visa Core Rules Section 11.7.

Your evaluation must consider:
1. Whether the dispute is valid (check for invalid dispute conditions per Section 11.7)
2. Whether time limits have been met
3. Whether required documentation has been provided
4. Whether the fraud type code has been properly reported
5. Whether EMV liability shift applies (conditions 10.1, 10.2)
6. The strength of the fraud claim based on available evidence

You MUST respond with valid JSON in this exact format:
{
    "is_valid": true/false,
    "validity_reason": "<explanation of validity determination>",
    "resolution": "<one of: issuer_win, acquirer_win, invalid_dispute>",
    "confidence": <float 0.0-1.0>,
    "rationale": "<detailed explanation citing specific Visa rules sections>",
    "rule_citations": [
        {
            "rule_section": "<e.g. 11.7.5>",
            "rule_description": "<what the rule says>",
            "is_satisfied": true/false,
            "details": "<how this rule applies to this case>"
        }
    ],
    "requires_human_review": true/false,
    "human_review_reason": "<reason if human review needed, null otherwise>"
}
"""


class FraudDisputeAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 10 (Fraud) dispute processing.

    Uses OpenAI to reason over Visa Core Rules Section 11.7 to evaluate
    fraud disputes, check validity, assess documentation, and render decisions.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.FRAUD)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate that this agent can handle the case."""
        if case.condition is None:
            return False
        return case.condition.category == DisputeCategory.FRAUD

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a fraud dispute using AI reasoning over Visa rules.

        The LLM evaluates the dispute against Section 11.7 of the Visa
        Core Rules, checking validity, documentation, time limits, and
        rendering a decision with rule citations.
        """
        self.logger.info(
            "Processing fraud dispute via AI: case=%s condition=%s",
            case.case_id,
            case.condition,
        )
        case.assigned_agent = self.agent_type.value
        case.advance_stage(
            DisputeLifecycleStage.RULE_EVALUATION,
            "AI fraud agent evaluating rules",
        )

        rules_context = get_fraud_rules()
        result = self._evaluate_dispute_with_llm(case, rules_context, _FRAUD_SYSTEM_PROMPT)

        all_evaluations: list[RuleEvaluationResult] = []
        for citation in result.get("rule_citations", []):
            eval_result = RuleEvaluationResult(
                rule_id=f"ai_fraud_{citation['rule_section'].replace('.', '_')}",
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
            "AI fraud dispute processed: case=%s resolution=%s confidence=%.2f",
            case.case_id,
            case.decision.resolution.value,
            case.decision.confidence_score,
        )
        return case
