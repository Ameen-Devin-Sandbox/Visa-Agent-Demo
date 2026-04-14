"""AI-powered consumer disputes processing agent (Category 13).

Uses OpenAI to reason over Visa Core Rules Section 11.10 to evaluate
consumer disputes and render decisions.

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
from src.llm.visa_rules import get_consumer_disputes_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
    DisputeResolution,
)

# TODO: Define _CONSUMER_SYSTEM_PROMPT — instruct the LLM to evaluate consumer
# disputes according to Visa Core Rules Section 11.10. Include condition-specific
# checks for all 13.x conditions. Require JSON output with same schema as other agents.
_CONSUMER_SYSTEM_PROMPT = ""


class ConsumerDisputesAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 13 (Consumer Disputes)."""

    def __init__(self) -> None:
        super().__init__(AgentType.CONSUMER_DISPUTES)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case.

        TODO: Return True only if case.condition belongs to DisputeCategory.CONSUMER_DISPUTES.
        """
        raise NotImplementedError("Module 3: Implement ConsumerDisputesAgent.validate")

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a consumer dispute using AI reasoning over Visa rules.

        TODO: Follow the same pattern as FraudDisputeAgent.process():
        Use get_consumer_disputes_rules() for rules context and
        _CONSUMER_SYSTEM_PROMPT for the system prompt.
        """
        raise NotImplementedError("Module 3: Implement ConsumerDisputesAgent.process")
