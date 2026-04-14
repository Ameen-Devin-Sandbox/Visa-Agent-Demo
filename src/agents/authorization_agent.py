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

# TODO: Define _AUTH_SYSTEM_PROMPT — instruct the LLM to evaluate authorization
# disputes according to Visa Core Rules Section 11.8. Include authorization-specific
# checks for CRB (11.1), declined auth (11.2), and no auth (11.3).
# Require JSON output matching the same schema as the fraud agent.
_AUTH_SYSTEM_PROMPT = ""


class AuthorizationDisputeAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 11 (Authorization) disputes."""

    def __init__(self) -> None:
        super().__init__(AgentType.AUTHORIZATION)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case.

        TODO: Return True only if case.condition belongs to DisputeCategory.AUTHORIZATION.
        """
        raise NotImplementedError("Module 3: Implement AuthorizationDisputeAgent.validate")

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process an authorization dispute using AI reasoning over Visa rules.

        TODO: Follow the same pattern as FraudDisputeAgent.process():
        1. Set assigned_agent, advance to RULE_EVALUATION
        2. Get rules via get_authorization_rules()
        3. Call _evaluate_dispute_with_llm()
        4. Parse citations, advance to DECISION
        5. Handle invalid disputes vs valid decisions
        6. Check human escalation, advance to final stage
        """
        raise NotImplementedError("Module 3: Implement AuthorizationDisputeAgent.process")
