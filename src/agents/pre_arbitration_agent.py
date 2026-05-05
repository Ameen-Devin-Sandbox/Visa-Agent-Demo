"""AI-powered pre-arbitration and arbitration processing agent.

Uses OpenAI to reason over Visa Core Rules Sections 11.2, 11.5, and 11.11
to evaluate pre-arbitration attempts, responses, and arbitration filings.
"""

from typing import Any

from src.agents.base_agent import BaseDisputeAgent
from src.llm.openai_client import chat_json
from src.llm.visa_rules import get_arbitration_rules, get_compelling_evidence_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeLifecycleStage,
    DisputeResolution,
)

# TODO: Define _PRE_ARB_SYSTEM_PROMPT — instruct the LLM to evaluate
# pre-arbitration and arbitration cases. The prompt should cover:
# 1. Compelling evidence evaluation (Section 11.5.2)
# 2. Timeliness of pre-arbitration/arbitration
# 3. Acquirer's grounds for pre-arbitration
# 4. Issuer's response adequacy
# 5. Whether escalation to arbitration is warranted
#
# Require JSON output with: has_compelling_evidence, resolution, confidence,
# rationale, rule_citations[], next_action, requires_human_review, human_review_reason
_PRE_ARB_SYSTEM_PROMPT = ""


class PreArbitrationAgent(BaseDisputeAgent):
    """AI-powered agent handling pre-arbitration and arbitration stages."""

    def __init__(self) -> None:
        super().__init__(AgentType.PRE_ARBITRATION)

    async def validate(self, case: DisputeCase) -> bool:
        """This agent handles cases in pre-arbitration or arbitration stages.

        TODO: Return True if case.stage is PRE_ARBITRATION, PRE_ARBITRATION_RESPONSE,
        or ARBITRATION.
        """
        raise NotImplementedError("Module 5: Implement PreArbitrationAgent.validate")

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a pre-arbitration or arbitration action using AI reasoning.

        TODO: Route based on case.stage:
        - PRE_ARBITRATION -> _process_pre_arbitration()
        - PRE_ARBITRATION_RESPONSE -> _process_pre_arbitration_response()
        - ARBITRATION -> _process_arbitration()
        """
        raise NotImplementedError("Module 5: Implement PreArbitrationAgent.process")

    async def _process_pre_arbitration(self, case: DisputeCase) -> DisputeCase:
        """Process a pre-arbitration attempt using AI evaluation.

        TODO: Increment pre_arbitration_attempts, get rules context from
        get_compelling_evidence_rules() + get_arbitration_rules(),
        evaluate with LLM, apply result.
        """
        raise NotImplementedError("Module 5: Implement _process_pre_arbitration")

    async def _process_pre_arbitration_response(self, case: DisputeCase) -> DisputeCase:
        """Process the issuer response to a pre-arbitration attempt using AI.

        TODO: Get rules context, evaluate with LLM, apply result.
        """
        raise NotImplementedError("Module 5: Implement _process_pre_arbitration_response")

    async def _process_arbitration(self, case: DisputeCase) -> DisputeCase:
        """Process an arbitration filing using AI evaluation.

        TODO: Set arbitration_filed=True, evaluate with LLM,
        create ESCALATED_ARBITRATION decision with human review required,
        advance to HUMAN_REVIEW stage.
        """
        raise NotImplementedError("Module 5: Implement _process_arbitration")

    def _apply_pre_arb_result(
        self, case: DisputeCase, result: dict[str, Any], prefix: str
    ) -> DisputeCase:
        """Apply the LLM evaluation result to the case.

        TODO: Parse rule citations, determine next_action from result:
        - "resolved" -> create decision, advance to RESOLVED
        - "awaiting_issuer_response" -> advance to PRE_ARBITRATION_RESPONSE
        - "escalate_arbitration" -> create ESCALATED_ARBITRATION decision, HUMAN_REVIEW
        - else -> human review
        """
        raise NotImplementedError("Module 5: Implement _apply_pre_arb_result")

    async def _evaluate_pre_arb_with_llm(
        self, case: DisputeCase, rules_context: str
    ) -> dict[str, Any]:
        """Use the LLM to evaluate a pre-arbitration/arbitration case.

        TODO: Build a user prompt with case details including:
        - Case stage, category, condition
        - Transaction details
        - Pre-arbitration attempts count
        - All evidence (separated by acquirer/issuer)
        - Issuer certification
        - Processing notes
        Call ``await chat_json(...)`` with _PRE_ARB_SYSTEM_PROMPT and return result.
        """
        raise NotImplementedError("Module 5: Implement _evaluate_pre_arb_with_llm")
