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

    def _evaluate_dispute_with_llm(
        self,
        case: DisputeCase,
        rules_context: str,
        system_prompt: str,
    ) -> dict[str, Any]:
        """Use OpenAI to evaluate a dispute against the Visa rules.

        Args:
            case: The dispute case to evaluate.
            rules_context: The relevant Visa rules text for this agent.
            system_prompt: The system prompt for the LLM.

        Returns:
            Parsed JSON dict with the LLM's evaluation.
        """
        if case.evidence:
            evidence_lines = [
                f"  - [{e.evidence_type}] {e.description} (provided by: {e.provided_by})"
                for e in case.evidence
            ]
            evidence_summary = "\n".join(evidence_lines)
        else:
            evidence_summary = "  No evidence provided"

        user_prompt = f"""\
Evaluate the following dispute case according to the Visa rules.

=== DISPUTE CASE ===
Case ID: {case.case_id}
Category: {case.category.value if case.category else 'Unknown'}
Condition: {case.condition.value if case.condition else 'Unknown'}
Transaction ID: {case.transaction.transaction_id}
Amount: {case.transaction.amount} {case.transaction.currency}
Merchant: {case.transaction.merchant_name}
Merchant Category Code: {case.transaction.merchant_category_code}
Transaction Date: {case.transaction.transaction_date}
Processing Date: {case.transaction.processing_date}
Environment: {case.transaction.environment.value}
Is Recurring: {case.transaction.is_recurring}
Authorization Code: {case.transaction.authorization_code or 'None'}
Authorization Response Code: {case.transaction.authorization_response_code or 'None'}
CVV Present: {case.transaction.cvv_present}
CVV Verified: {case.transaction.cvv_verified}
3-D Secure Authenticated: {case.transaction.three_d_secure_authenticated}
Is Chip Card: {case.transaction.is_chip_card}
Is Chip Initiated: {case.transaction.is_chip_initiated}
Is Contactless: {case.transaction.is_contactless}
Is Token Transaction: {case.transaction.is_token_transaction}
Is Fallback Transaction: {case.transaction.is_fallback_transaction}

Cardholder Statement: {case.cardholder.cardholder_statement or 'No statement provided'}
Fraud Type Code: {case.fraud_type_code.value if case.fraud_type_code else 'None'}
Dispute Amount: {case.dispute_amount}
Dispute Filed Date: {case.dispute_filed_date}

Evidence:
{evidence_summary}

=== VISA RULES REFERENCE ===
{rules_context}

Evaluate this dispute and provide your analysis as JSON.
"""
        return chat_json(system_prompt, user_prompt)
