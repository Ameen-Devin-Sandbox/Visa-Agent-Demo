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


_SYSTEM_PROMPT = """\
You are an expert Visa dispute categorization agent. Your job is to analyze \
dispute cases and determine the correct dispute category and condition based on \
the Visa Core Rules.

You must categorize each dispute into exactly ONE of these categories:
- Category 10 (Fraud): Conditions 10.1, 10.2, 10.3, 10.4, 10.5
- Category 11 (Authorization): Conditions 11.1, 11.2, 11.3
- Category 12 (Processing Errors): Conditions 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
- Category 13 (Consumer Disputes): Conditions 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, \
13.7, 13.8, 13.9

KEY CATEGORIZATION PRINCIPLES from the Visa Rules:
1. Fraud (Cat 10): The cardholder denies authorizing or participating in the \
transaction. Fraud type codes, unauthorized charges, stolen cards, identity theft.
2. Authorization (Cat 11): Issues with the authorization process itself - card on \
recovery bulletin, declined authorization that was processed anyway, no authorization \
obtained.
3. Processing Errors (Cat 12): Technical/processing mistakes - wrong transaction code, \
wrong currency, wrong account number, wrong amount, duplicate processing, invalid data.
4. Consumer Disputes (Cat 13): The cardholder participated in the transaction but has \
a dispute about what was received or billed - merchandise not received, cancelled \
recurring, not as described, counterfeit merchandise, misrepresentation, credit not \
processed, etc.

IMPORTANT DISTINCTIONS:
- "Counterfeit merchandise" (received fake goods) = 13.4 Consumer Dispute, NOT fraud
- "Counterfeit card" (card was counterfeited) = 10.1 Fraud
- Cancelled subscription still being charged = 13.2 Consumer Dispute, NOT authorization
- Missing authorization code alone does not make it an authorization dispute if there \
are stronger consumer dispute signals

You MUST respond with valid JSON in this exact format:
{
    "category": "<category code: 10, 11, 12, or 13>",
    "condition": "<condition code: e.g. 10.4, 13.2>",
    "confidence": <float 0.0-1.0>,
    "rationale": "<explanation citing specific Visa rules>",
    "alternative_conditions": ["<other possible condition codes>"]
}
"""


def categorize_dispute(case: DisputeCase) -> CategorizationResult:
    """Categorize a dispute using OpenAI reasoning over Visa rules.

    The LLM analyzes the transaction details, cardholder statement, evidence,
    and fraud indicators against the Visa Core Rules to determine the
    appropriate dispute category and condition.
    """
    user_prompt = _build_case_prompt(case)

    logger.info(
        "Categorizing dispute via AI: case=%s merchant=%s amount=%.2f",
        case.transaction.transaction_id,
        case.transaction.merchant_name,
        case.transaction.amount,
    )

    result = chat_json(_SYSTEM_PROMPT, user_prompt)

    category = DisputeCategory(result["category"])
    condition = DisputeCondition(result["condition"])
    confidence = float(result["confidence"])
    rationale = result["rationale"]
    alternatives = [
        DisputeCondition(c) for c in result.get("alternative_conditions", []) if c
    ]

    logger.info(
        "AI categorization: %s/%s (confidence: %.2f) - %s",
        category.value,
        condition.value,
        confidence,
        rationale[:100],
    )

    return CategorizationResult(
        category=category,
        condition=condition,
        confidence=confidence,
        rationale=rationale,
        alternative_conditions=alternatives,
    )


def _build_case_prompt(case: DisputeCase) -> str:
    """Build the user prompt with case details and relevant Visa rules context."""
    if case.evidence:
        evidence_lines = [
            f"  - [{e.evidence_type}] {e.description} (provided by: {e.provided_by})"
            for e in case.evidence
        ]
        evidence_summary = "\n".join(evidence_lines)
    else:
        evidence_summary = "  No evidence provided"

    rules_context = get_categorization_context()

    return f"""\
Analyze the following dispute case and determine the correct Visa dispute \
category and condition.

=== DISPUTE CASE ===
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

Evidence:
{evidence_summary}

=== VISA RULES REFERENCE ===
{rules_context}

Based on the case details and the Visa rules above, determine the correct \
dispute category and condition. Provide your analysis as JSON.
"""
