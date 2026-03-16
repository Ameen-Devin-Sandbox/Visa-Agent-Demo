"""Base agent class for dispute processing sub-agents."""

import logging
from abc import ABC, abstractmethod

from src.models.dispute import DisputeCase, DisputeDecision, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeResolution,
)


class BaseDisputeAgent(ABC):
    """Abstract base class for all dispute processing sub-agents.

    Each sub-agent specializes in processing disputes for a specific
    category or lifecycle stage. Sub-agents encode domain expertise
    and apply Visa rules deterministically.
    """

    def __init__(self, agent_type: AgentType) -> None:
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"agent.{agent_type.value}")

    @abstractmethod
    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a dispute case through this agent's specialized logic.

        Args:
            case: The dispute case to process.

        Returns:
            The updated dispute case after processing.
        """
        ...

    @abstractmethod
    async def validate(self, case: DisputeCase) -> bool:
        """Validate that this agent can handle the given case.

        Args:
            case: The dispute case to validate.

        Returns:
            True if this agent can process the case.
        """
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
        """Create a dispute decision with proper audit trail."""
        return DisputeDecision(
            resolution=resolution,
            rationale=rationale,
            rule_citations=rule_evaluations,
            confidence_score=confidence,
            requires_human_review=requires_human_review,
            human_review_reason=human_review_reason,
            decided_by=self.agent_type.value,
        )

    def _should_escalate_to_human(self, confidence: float, case: DisputeCase) -> bool:
        """Determine if a case should be escalated to human review.

        Cases are escalated when:
        - Confidence is below threshold (0.70)
        - The dispute amount exceeds a high-value threshold
        - Multiple alternative conditions were identified
        """
        if confidence < 0.70:
            return True
        return bool(case.dispute_amount and case.dispute_amount > 25000)
