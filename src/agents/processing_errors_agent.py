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

# TODO: Define _PROC_ERRORS_SYSTEM_PROMPT — instruct the LLM to evaluate processing
# error disputes according to Visa Core Rules Section 11.9. Include condition-specific
# checks for all 12.x conditions. Require JSON output with same schema as other agents.
_PROC_ERRORS_SYSTEM_PROMPT = ""


class ProcessingErrorsAgent(BaseDisputeAgent):
    """AI-powered agent specializing in Category 12 (Processing Errors) disputes."""

    def __init__(self) -> None:
        super().__init__(AgentType.PROCESSING_ERRORS)

    async def validate(self, case: DisputeCase) -> bool:
        """Validate this agent can handle the case.

        TODO: Return True only if case.condition belongs to DisputeCategory.PROCESSING_ERRORS.
        """
        raise NotImplementedError("Module 3: Implement ProcessingErrorsAgent.validate")

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a processing error dispute using AI reasoning over Visa rules.

        TODO: Follow the same pattern as FraudDisputeAgent.process():
        Use get_processing_errors_rules() for rules context and
        _PROC_ERRORS_SYSTEM_PROMPT for the system prompt.
        """
        raise NotImplementedError("Module 3: Implement ProcessingErrorsAgent.process")
