"""AI-powered dispute categorization engine.

Uses OpenAI to analyze incoming dispute cases against the Visa Core Rules
document (Section 11.6-11.10) and determine the appropriate dispute category
and condition.

This replaces the previous hardcoded rules engine with an LLM-powered
approach that reasons directly over the Visa rules text.
"""

import logging
from dataclasses import dataclass

from src.llm.openai_client import chat_json
from src.llm.visa_rules import (
    get_categorization_context,
    get_category_conditions,
    get_category_summaries,
)
from src.models.dispute import DisputeCase
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
)

logger = logging.getLogger(__name__)


@dataclass
class CategorizationResult:
    """Result of dispute categorization."""

    category: DisputeCategory
    condition: DisputeCondition
    confidence: float
    rationale: str
    alternative_conditions: list[DisputeCondition]


# TODO: Define _SYSTEM_PROMPT — a system prompt that instructs the LLM to categorize
# disputes into one of the 4 Visa categories (10-Fraud, 11-Authorization,
# 12-Processing Errors, 13-Consumer Disputes) and their specific conditions.
#
# The prompt should:
# 1. List all valid categories and conditions
# 2. Explain key categorization principles from the Visa rules
# 3. Clarify important distinctions (e.g., counterfeit merchandise vs counterfeit card)
# 4. Require JSON output with: category, condition, confidence, rationale, alternative_conditions
_SYSTEM_PROMPT = ""


async def categorize_dispute(case: DisputeCase) -> CategorizationResult:
    """Categorize a dispute using OpenAI reasoning over Visa rules.

    The LLM analyzes the transaction details, cardholder statement, evidence,
    and fraud indicators against the Visa Core Rules to determine the
    appropriate dispute category and condition.

    TODO: Implement this function using a two-stage categorization to reduce
    the token payload (~75% reduction vs. the legacy single-call approach):

    Stage 1 - Pick a category:
        Build a prompt using ``get_category_summaries()`` and call
        ``await chat_json(...)`` to have the LLM choose one of the four
        categories (10/11/12/13).

    Stage 2 - Pick a condition within that category:
        Build a follow-up prompt using ``get_category_conditions(category)``
        and call ``await chat_json(...)`` to have the LLM pick the specific
        condition. Parse the final JSON response into a CategorizationResult.

    The legacy single-call approach used ``get_categorization_context()`` and
    is still importable for reference, but it ships all 23 sub-conditions in
    every request and should not be used for new implementations.
    """
    raise NotImplementedError("Module 1: Implement categorize_dispute")


def _build_case_prompt(case: DisputeCase) -> str:
    """Build the user prompt with case details and relevant Visa rules context.

    TODO: Implement this function to format the dispute case into a prompt:
    - Include transaction details (ID, amount, merchant, dates, environment, etc.)
    - Include cardholder statement and fraud type code
    - Include evidence summary
    - Append the Visa rules context from get_categorization_context()
    """
    raise NotImplementedError("Module 1: Implement _build_case_prompt")
