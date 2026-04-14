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

# TODO: Define _FRAUD_SYSTEM_PROMPT — instruct the LLM to evaluate fraud disputes
# according to Visa Core Rules Section 11.7. The prompt should tell the LLM to:
# 1. Check validity (invalid dispute conditions per Section 11.7)
# 2. Check time limits
# 3. Check required documentation and fraud type code
# 4. Check EMV liability shift (conditions 10.1, 10.2)
# 5. Assess evidence strength
# 6. Return JSON with: is_valid, validity_reason, resolution, confidence,
#    rationale, rule_citations[], requires_human_review, human_review_reason
_FRAUD_SYSTEM_PROMPT = ""


class FraudDisputeAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 10 (Fraud) dispute processing."""

    def __init__(self) -> None:
        super().__init__(AgentType.FRAUD)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate that this agent can handle the case.

        TODO: Return True only if case.condition is set and belongs to
        DisputeCategory.FRAUD (Category 10).
        """
        raise NotImplementedError("Module 2: Implement FraudDisputeAgent.validate")

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a fraud dispute using AI reasoning over Visa rules.

        TODO: Implement the full processing pipeline:
        1. Set case.assigned_agent to this agent's type
        2. Advance stage to RULE_EVALUATION
        3. Get fraud rules context via get_fraud_rules()
        4. Call self._evaluate_dispute_with_llm() with the rules and system prompt
        5. Parse rule_citations from the result into RuleEvaluationResult objects
        6. Advance stage to DECISION
        7. If result says dispute is invalid -> create INVALID_DISPUTE decision, resolve
        8. Otherwise -> create decision based on result resolution/confidence
        9. Check _should_escalate_to_human() for human review
        10. Advance to RESOLVED or HUMAN_REVIEW stage
        11. Return the updated case
        """
        raise NotImplementedError("Module 2: Implement FraudDisputeAgent.process")
