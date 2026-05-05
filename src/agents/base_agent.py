"""Base agent class for AI-powered dispute processing sub-agents.

Each agent uses OpenAI to reason over the Visa Core Rules document
to validate disputes and render decisions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.llm.openai_client import chat_json
from src.models.dispute import DisputeCase, DisputeDecision, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeResolution,
)


class BaseDisputeAgent(ABC):
    """Abstract base class for all dispute processing sub-agents.

    Each sub-agent specializes in processing disputes for a specific
    category or lifecycle stage. Sub-agents use OpenAI to reason over
    the Visa Core Rules document and render decisions.
    """

    def __init__(self, agent_type: AgentType) -> None:
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"agent.{agent_type.value}")

    @abstractmethod
    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a dispute case through this agent's specialized logic."""
        ...

    @abstractmethod
    async def validate(self, case: DisputeCase) -> bool:
        """Validate that this agent can handle the given case."""
        ...

    def create_decision(
        self,
        resolution: DisputeResolution,
        rationale: str,
        rule_evaluations: list[RuleEvaluationResult],
        confidence: float,
        requires_human_review: bool = False,
        human_review_reason: str | None = None,
    ) -> DisputeDecision:
        """Create a dispute decision with proper audit trail.

        TODO: Implement this method to return a DisputeDecision with:
        - The given resolution, rationale, confidence
        - rule_citations from rule_evaluations
        - Human review flags
        - decided_by set to self.agent_type.value
        """
        raise NotImplementedError("Module 2: Implement create_decision")

    def _should_escalate_to_human(self, confidence: float, case: DisputeCase) -> bool:
        """Determine if a case should be escalated to human review.

        TODO: Implement escalation logic:
        - Confidence below 0.70 -> escalate
        - Dispute amount over $25,000 -> escalate
        """
        raise NotImplementedError("Module 2: Implement _should_escalate_to_human")

    async def _evaluate_dispute_with_llm(
        self,
        case: DisputeCase,
        rules_context: str,
        system_prompt: str,
    ) -> dict[str, Any]:
        """Use OpenAI to evaluate a dispute against the Visa rules.

        TODO: Implement this method:
        1. Build a user prompt with all case details (case ID, category, condition,
           transaction details, cardholder statement, evidence, etc.)
        2. Append the rules_context as reference
        3. Call ``await chat_json(system_prompt, user_prompt)`` and return the result
        """
        raise NotImplementedError("Module 2: Implement _evaluate_dispute_with_llm")
