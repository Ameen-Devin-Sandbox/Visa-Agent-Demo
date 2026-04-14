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
from src.llm.visa_rules import get_categorization_context
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


def categorize_dispute(case: DisputeCase) -> CategorizationResult:
    """Categorize a dispute using OpenAI reasoning over Visa rules.

    The LLM analyzes the transaction details, cardholder statement, evidence,
    and fraud indicators against the Visa Core Rules to determine the
    appropriate dispute category and condition.

    TODO: Implement this function:
    1. Build a user prompt with case details using _build_case_prompt()
    2. Call chat_json() with the system prompt and user prompt
    3. Parse the JSON response into a CategorizationResult
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
