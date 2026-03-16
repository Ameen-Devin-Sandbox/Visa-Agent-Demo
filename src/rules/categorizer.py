"""Dispute categorization engine.

Analyzes incoming dispute cases and determines the appropriate dispute
category and condition based on Visa Core Rules Section 11.6-11.10.

Uses rule-based logic as the primary categorization path, with an optional
OpenAI-powered fallback for ambiguous cases where confidence is low.
"""

import json
import logging
import os
from dataclasses import dataclass

from src.models.dispute import DisputeCase
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    FraudTypeCode,
    TransactionEnvironment,
)

logger = logging.getLogger(__name__)

# Shared constant: words that indicate the dispute is about physical merchandise,
# not about the card itself being counterfeit/compromised.
_MERCHANDISE_CONTEXT_WORDS = [
    "received",
    "merchandise",
    "product",
    "goods",
    "item",
    "watch",
    "bag",
    "shoe",
    "serial number",
    "authentication",
    "brand",
    "quality",
    "material",
]


@dataclass
class CategorizationResult:
    """Result of dispute categorization."""

    category: DisputeCategory
    condition: DisputeCondition
    confidence: float
    rationale: str
    alternative_conditions: list[DisputeCondition]


def categorize_dispute(case: DisputeCase) -> CategorizationResult:
    """Categorize a dispute based on transaction details and cardholder claims.

    This implements the decision logic from Visa Core Rules Section 11.6
    to determine the appropriate dispute category and condition.

    The categorization follows this refined hierarchy:
    1. Check for consumer dispute signals first (to prevent misrouting)
    2. Check for fraud indicators (Category 10)
    3. Check for authorization issues (Category 11)
    4. Check for processing errors (Category 12)
    5. Default to consumer disputes (Category 13)

    When rule-based confidence is low, an OpenAI-powered fallback is used
    to improve categorization accuracy.
    """
    alternatives: list[DisputeCondition] = []

    # Priority 0: Check for clear consumer dispute signals that should NOT be
    # routed to fraud or authorization. This prevents misrouting cases like
    # "received counterfeit merchandise" (13.4) or "cancelled subscription" (13.2).
    if _is_consumer_dispute(case):
        condition, confidence, rationale = _categorize_consumer_dispute(case)
        return CategorizationResult(
            category=DisputeCategory.CONSUMER_DISPUTES,
            condition=condition,
            confidence=confidence,
            rationale=rationale,
            alternative_conditions=alternatives,
        )

    # Priority 1: Fraud disputes (Category 10)
    if _is_fraud_dispute(case):
        condition, confidence, rationale = _categorize_fraud(case)
        # Collect alternative fraud conditions
        for alt in _get_alternative_fraud_conditions(case, condition):
            alternatives.append(alt)
        return CategorizationResult(
            category=DisputeCategory.FRAUD,
            condition=condition,
            confidence=confidence,
            rationale=rationale,
            alternative_conditions=alternatives,
        )

    # Priority 2: Authorization disputes (Category 11)
    if _is_authorization_dispute(case):
        condition, confidence, rationale = _categorize_authorization(case)
        return CategorizationResult(
            category=DisputeCategory.AUTHORIZATION,
            condition=condition,
            confidence=confidence,
            rationale=rationale,
            alternative_conditions=alternatives,
        )

    # Priority 3: Processing error disputes (Category 12)
    if _is_processing_error_dispute(case):
        condition, confidence, rationale = _categorize_processing_error(case)
        return CategorizationResult(
            category=DisputeCategory.PROCESSING_ERRORS,
            condition=condition,
            confidence=confidence,
            rationale=rationale,
            alternative_conditions=alternatives,
        )

    # Default: Consumer disputes (Category 13)
    condition, confidence, rationale = _categorize_consumer_dispute(case)
    result = CategorizationResult(
        category=DisputeCategory.CONSUMER_DISPUTES,
        condition=condition,
        confidence=confidence,
        rationale=rationale,
        alternative_conditions=alternatives,
    )

    # If rule-based confidence is low, try OpenAI-powered categorization
    if result.confidence < 0.70:
        llm_result = _try_llm_categorization(case)
        if llm_result is not None and llm_result.confidence > result.confidence:
            logger.info(
                "LLM categorization overrode rule-based: %s/%s (%.2f) -> %s/%s (%.2f)",
                result.category.value,
                result.condition.value,
                result.confidence,
                llm_result.category.value,
                llm_result.condition.value,
                llm_result.confidence,
            )
            return llm_result

    return result


def _is_consumer_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute is clearly a consumer dispute.

    This check runs before fraud/authorization to prevent misrouting cases where
    consumer-dispute keywords (e.g., 'counterfeit merchandise', 'cancelled subscription')
    overlap with fraud or authorization indicators.

    Yields to explicit fraud signals: if ``fraud_type_code`` is set or explicit
    fraud language ("unauthorized", "fraud", "stolen", etc.) appears in the
    cardholder statement, this returns False so the fraud path runs instead.
    """
    # Never override an explicit fraud type code from the issuer
    if case.fraud_type_code is not None:
        return False

    statement = (case.cardholder.cardholder_statement or "").lower()
    txn = case.transaction

    # If the cardholder explicitly mentions fraud / unauthorized activity,
    # defer to the fraud categorizer even if consumer signals are also present.
    explicit_fraud_language = [
        "unauthorized",
        "fraud",
        "did not authorize",
        "did not make",
        "stolen",
        "lost",
        "not mine",
        "identity theft",
    ]
    if any(word in statement for word in explicit_fraud_language):
        return False

    # Counterfeit merchandise: cardholder received goods that are fake/counterfeit.
    # Distinguished from fraud by context - merchandise-related words nearby.
    if ("counterfeit" in statement or "fake" in statement) and any(
        word in statement for word in _MERCHANDISE_CONTEXT_WORDS
    ):
        return True

    # Cancelled recurring subscription: recurring flag + cancellation language
    if txn.is_recurring and (
        "cancel" in statement
        or "stopped" in statement
        or "subscription" in statement
        or "still being charged" in statement
    ):
        return True

    # Not as described / defective with merchandise context
    if "not as described" in statement or "defective" in statement:
        return True

    # Merchandise not received (strong consumer signal)
    if (
        "not received" in statement
        or "never received" in statement
        or "did not arrive" in statement
    ) and "authorize" not in statement:
        return True

    # Credit/refund not processed
    return "credit not" in statement or "refund not" in statement or "no refund" in statement


def _is_fraud_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute involves fraud.

    Checks for fraud indicators while excluding cases that are better
    classified as consumer disputes (e.g., receiving counterfeit merchandise).
    """
    # Fraud type code explicitly reported by issuer - strong fraud signal
    if case.fraud_type_code is not None:
        return True

    statement = (case.cardholder.cardholder_statement or "").lower()

    # "counterfeit" in a merchandise context is a consumer dispute, not fraud.
    # Only treat "counterfeit" as fraud when it refers to the card itself.
    fraud_indicators = [
        "unauthorized",
        "fraud",
        "did not authorize",
        "did not make",
        "stolen",
        "lost",
        "not mine",
        "identity theft",
    ]
    if any(indicator in statement for indicator in fraud_indicators):
        return True

    # "counterfeit" only counts as fraud when referring to the card, not merchandise
    return "counterfeit" in statement and not any(
        word in statement for word in _MERCHANDISE_CONTEXT_WORDS
    )


def _is_authorization_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute involves authorization issues.

    A missing authorization_code alone is not sufficient to classify as an
    authorization dispute - many e-commerce and recurring transactions may
    not have an explicit auth code in the dispute data. We require additional
    signals like a declined response code or authorization-specific language.
    """
    txn = case.transaction
    statement = (case.cardholder.cardholder_statement or "").lower()

    # Declined authorization - strong signal
    if txn.authorization_response_code and not txn.authorization_response_code.startswith("0"):
        return True

    # Statement-based authorization indicators
    auth_indicators = [
        "declined",
        "no authorization",
        "over limit",
        "expired card",
        "card recovery",
        "late presentment",
    ]
    if any(indicator in statement for indicator in auth_indicators):
        return True

    # Missing authorization code is only an auth dispute signal when the
    # cardholder statement also references authorization issues, or when
    # there are no stronger consumer/processing signals present.
    if txn.authorization_code is None:
        # Don't classify as auth dispute if there are consumer dispute signals
        consumer_signals = [
            "cancel",
            "subscription",
            "not received",
            "defective",
            "counterfeit",
            "fake",
            "refund",
            "return",
            "not as described",
            "still being charged",
            "merchandise",
        ]
        if any(signal in statement for signal in consumer_signals):
            return False
        # No consumer signals - treat missing auth code as authorization dispute
        return not txn.is_recurring

    return False


def _is_processing_error_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute involves processing errors."""
    statement = (case.cardholder.cardholder_statement or "").lower()
    error_indicators = [
        "wrong amount",
        "incorrect amount",
        "duplicate",
        "charged twice",
        "wrong currency",
        "incorrect currency",
        "wrong account",
        "paid by other means",
        "invalid data",
        "incorrect code",
    ]
    return any(indicator in statement for indicator in error_indicators)


def _categorize_fraud(
    case: DisputeCase,
) -> tuple[DisputeCondition, float, str]:
    """Determine the specific fraud condition (10.1-10.5)."""
    txn = case.transaction

    # 10.1: EMV Liability Shift Counterfeit Fraud
    if (
        case.fraud_type_code == FraudTypeCode.COUNTERFEIT
        and txn.environment == TransactionEnvironment.CARD_PRESENT
        and txn.is_chip_card
    ):
        chip_device_issue = txn.terminal_entry_capability != "5" or (
            txn.is_chip_initiated and not txn.full_chip_data_transmitted
        )
        if chip_device_issue:
            return (
                DisputeCondition.EMV_COUNTERFEIT_FRAUD,
                0.95,
                "EMV Liability Shift: Counterfeit card used at non-chip or improperly configured terminal",
            )

    # 10.2: EMV Liability Shift Non-Counterfeit Fraud
    if (
        case.fraud_type_code
        in (FraudTypeCode.LOST, FraudTypeCode.STOLEN, FraudTypeCode.NOT_RECEIVED)
        and txn.environment == TransactionEnvironment.CARD_PRESENT
        and txn.is_chip_card
    ):
        return (
            DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            0.90,
            "EMV Liability Shift: Lost/stolen/NRI card used at terminal without proper PIN verification",
        )

    # 10.3: Other Fraud - Card-Present
    if txn.environment == TransactionEnvironment.CARD_PRESENT:
        return (
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
            0.85,
            "Fraud in card-present environment not qualifying for EMV liability shift",
        )

    # 10.4: Other Fraud - Card-Absent (default for CNP fraud)
    if txn.environment in (
        TransactionEnvironment.CARD_ABSENT,
        TransactionEnvironment.ECOMMERCE,
        TransactionEnvironment.MOTO,
    ):
        return (
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            0.90,
            "Fraud in card-not-present environment",
        )

    # Fallback
    return (
        DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
        0.60,
        "Fraud dispute defaulting to card-absent; manual review recommended",
    )


def _get_alternative_fraud_conditions(
    case: DisputeCase,
    primary: DisputeCondition,
) -> list[DisputeCondition]:
    """Get alternative fraud conditions that might also apply."""
    alternatives: list[DisputeCondition] = []
    txn = case.transaction

    if primary != DisputeCondition.VISA_FRAUD_MONITORING:
        # 10.5 can be filed in addition to other conditions per 11.2.1
        alternatives.append(DisputeCondition.VISA_FRAUD_MONITORING)

    if primary == DisputeCondition.OTHER_FRAUD_CARD_PRESENT and txn.is_chip_card:
        alternatives.append(DisputeCondition.EMV_COUNTERFEIT_FRAUD)
        alternatives.append(DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD)

    return alternatives


def _categorize_authorization(
    case: DisputeCase,
) -> tuple[DisputeCondition, float, str]:
    """Determine the specific authorization condition (11.1-11.3)."""
    txn = case.transaction
    statement = (case.cardholder.cardholder_statement or "").lower()

    # 11.1: Card Recovery Bulletin
    if "card recovery" in statement or "crb" in statement:
        return (
            DisputeCondition.CARD_RECOVERY_BULLETIN,
            0.85,
            "Card was listed on the Card Recovery Bulletin at the time of the Transaction",
        )

    # 11.2: Declined Authorization
    if txn.authorization_response_code and not txn.authorization_response_code.startswith("0"):
        return (
            DisputeCondition.DECLINED_AUTHORIZATION,
            0.95,
            f"Authorization was declined (response code: {txn.authorization_response_code})",
        )

    # 11.3: No Authorization / Late Presentment
    if txn.authorization_code is None:
        return (
            DisputeCondition.NO_AUTHORIZATION,
            0.90,
            "No valid authorization was obtained for the Transaction",
        )

    return (
        DisputeCondition.NO_AUTHORIZATION,
        0.60,
        "Authorization dispute; defaulting to No Authorization. Manual review recommended.",
    )


def _categorize_processing_error(
    case: DisputeCase,
) -> tuple[DisputeCondition, float, str]:
    """Determine the specific processing error condition (12.2-12.7)."""
    statement = (case.cardholder.cardholder_statement or "").lower()

    if (
        "duplicate" in statement
        or "charged twice" in statement
        or "paid by other means" in statement
    ):
        return (
            DisputeCondition.DUPLICATE_PROCESSING,
            0.90,
            "Transaction was processed more than once or paid by other means",
        )

    if "wrong amount" in statement or "incorrect amount" in statement:
        return (
            DisputeCondition.INCORRECT_AMOUNT,
            0.90,
            "Transaction amount does not match the agreed-upon amount",
        )

    if "wrong currency" in statement or "incorrect currency" in statement:
        return (
            DisputeCondition.INCORRECT_CURRENCY,
            0.90,
            "Transaction was processed in the wrong currency",
        )

    if "wrong account" in statement or "incorrect account" in statement:
        return (
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER,
            0.85,
            "Transaction was posted to the wrong account",
        )

    if "incorrect code" in statement or "wrong code" in statement:
        return (
            DisputeCondition.INCORRECT_TRANSACTION_CODE,
            0.80,
            "Incorrect transaction code was used",
        )

    if "invalid data" in statement:
        return (
            DisputeCondition.INVALID_DATA,
            0.80,
            "Transaction contains invalid data",
        )

    return (
        DisputeCondition.INCORRECT_AMOUNT,
        0.50,
        "Processing error type unclear; defaulting to incorrect amount. Manual review recommended.",
    )


def _categorize_consumer_dispute(
    case: DisputeCase,
) -> tuple[DisputeCondition, float, str]:
    """Determine the specific consumer dispute condition (13.1-13.9)."""
    txn = case.transaction
    statement = (case.cardholder.cardholder_statement or "").lower()

    # 13.9: Non-Receipt of Cash at ATM
    if txn.environment == TransactionEnvironment.ATM:
        return (
            DisputeCondition.NON_RECEIPT_CASH_ATM,
            0.95,
            "Cash not received at ATM",
        )

    # 13.1: Merchandise/Services Not Received
    if (
        "not received" in statement
        or "never received" in statement
        or "did not arrive" in statement
    ):
        return (
            DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            0.90,
            "Merchandise or services were not received by the cardholder",
        )

    # 13.2: Cancelled Recurring Transaction
    if txn.is_recurring and ("cancel" in statement or "stopped" in statement):
        return (
            DisputeCondition.CANCELLED_RECURRING,
            0.90,
            "Recurring transaction was billed after cancellation",
        )

    # 13.3: Not as Described or Defective
    if "not as described" in statement or "defective" in statement or "different" in statement:
        return (
            DisputeCondition.NOT_AS_DESCRIBED,
            0.85,
            "Merchandise/services not as described or defective",
        )

    # 13.4: Counterfeit Merchandise
    if "counterfeit" in statement or "fake" in statement:
        return (
            DisputeCondition.COUNTERFEIT_MERCHANDISE,
            0.85,
            "Merchandise is counterfeit",
        )

    # 13.5: Misrepresentation
    if "misrepresent" in statement or "misleading" in statement or "false" in statement:
        return (
            DisputeCondition.MISREPRESENTATION,
            0.80,
            "Merchant misrepresented the merchandise or services",
        )

    # 13.6: Credit Not Processed
    if "credit not" in statement or "refund not" in statement or "no refund" in statement:
        return (
            DisputeCondition.CREDIT_NOT_PROCESSED,
            0.85,
            "Expected credit/refund was not processed by the merchant",
        )

    # 13.7: Cancelled Merchandise/Services
    if "cancel" in statement or "return" in statement:
        return (
            DisputeCondition.CANCELLED_MERCHANDISE,
            0.80,
            "Merchandise/services were cancelled or returned",
        )

    # 13.8: Original Credit Transaction Not Accepted
    if "oct" in statement or "original credit" in statement:
        return (
            DisputeCondition.OCT_NOT_ACCEPTED,
            0.80,
            "Original Credit Transaction was not accepted",
        )

    # Default
    return (
        DisputeCondition.MERCHANDISE_NOT_RECEIVED,
        0.40,
        "Consumer dispute type unclear; defaulting to merchandise not received. Manual review recommended.",
    )


# --- OpenAI-powered categorization fallback ---

_LLM_CATEGORIZATION_PROMPT = """You are a Visa dispute categorization expert. Analyze the following dispute and determine the correct category and condition.

Visa Dispute Categories and Conditions:
- Category 10 (Fraud): 10.1 EMV Counterfeit, 10.2 EMV Non-Counterfeit, 10.3 Other Fraud Card-Present, 10.4 Other Fraud Card-Absent, 10.5 Visa Fraud Monitoring
- Category 11 (Authorization): 11.1 Card Recovery Bulletin, 11.2 Declined Authorization, 11.3 No Authorization/Late Presentment
- Category 12 (Processing Errors): 12.2 Incorrect Transaction Code, 12.3 Incorrect Currency, 12.4 Incorrect Account Number, 12.5 Incorrect Amount, 12.6 Duplicate Processing/Paid by Other Means, 12.7 Invalid Data
- Category 13 (Consumer Disputes): 13.1 Merchandise Not Received, 13.2 Cancelled Recurring, 13.3 Not as Described/Defective, 13.4 Counterfeit Merchandise, 13.5 Misrepresentation, 13.6 Credit Not Processed, 13.7 Cancelled Merchandise/Services, 13.8 OCT Not Accepted, 13.9 Non-Receipt of Cash at ATM

Dispute Details:
- Transaction ID: {transaction_id}
- Amount: {amount} {currency}
- Merchant: {merchant_name} (MCC: {mcc})
- Environment: {environment}
- Is Recurring: {is_recurring}
- Authorization Code: {auth_code}
- Authorization Response: {auth_response}
- Cardholder Statement: {statement}
- Evidence: {evidence}

Respond with a JSON object containing:
- "category": the category number as a string (e.g., "10", "11", "12", "13")
- "condition": the condition code as a string (e.g., "10.4", "13.1")
- "confidence": a float between 0 and 1
- "rationale": a brief explanation

Respond ONLY with the JSON object, no other text."""


def _try_llm_categorization(case: DisputeCase) -> CategorizationResult | None:
    """Attempt to categorize a dispute using OpenAI when rule-based confidence is low.

    Returns None if OpenAI is not configured or the call fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.debug("OpenAI API key not configured; skipping LLM categorization")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        evidence_summary = "; ".join(f"{e.evidence_type}: {e.description}" for e in case.evidence)

        prompt = _LLM_CATEGORIZATION_PROMPT.format(
            transaction_id=case.transaction.transaction_id,
            amount=case.transaction.amount,
            currency=case.transaction.currency,
            merchant_name=case.transaction.merchant_name,
            mcc=case.transaction.merchant_category_code,
            environment=case.transaction.environment.value,
            is_recurring=case.transaction.is_recurring,
            auth_code=case.transaction.authorization_code or "None",
            auth_response=case.transaction.authorization_response_code or "None",
            statement=case.cardholder.cardholder_statement or "No statement provided",
            evidence=evidence_summary or "No evidence provided",
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )

        content = response.choices[0].message.content
        if content is None:
            return None

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)

        category = DisputeCategory(result["category"])
        condition = DisputeCondition(result["condition"])
        confidence = float(result["confidence"])
        rationale = f"[LLM] {result['rationale']}"

        logger.info(
            "LLM categorization result: %s/%s (confidence: %.2f)",
            category.value,
            condition.value,
            confidence,
        )

        return CategorizationResult(
            category=category,
            condition=condition,
            confidence=confidence,
            rationale=rationale,
            alternative_conditions=[],
        )

    except Exception:
        logger.exception("LLM categorization failed")
        return None
