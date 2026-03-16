"""Dispute categorization engine.

Analyzes incoming dispute cases and determines the appropriate dispute
category and condition based on Visa Core Rules Section 11.6-11.10.
"""

from dataclasses import dataclass

from src.models.dispute import DisputeCase
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    FraudTypeCode,
    TransactionEnvironment,
)


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

    The categorization follows this hierarchy:
    1. Check for fraud indicators (Category 10)
    2. Check for authorization issues (Category 11)
    3. Check for processing errors (Category 12)
    4. Default to consumer disputes (Category 13)
    """
    alternatives: list[DisputeCondition] = []

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
    return CategorizationResult(
        category=DisputeCategory.CONSUMER_DISPUTES,
        condition=condition,
        confidence=confidence,
        rationale=rationale,
        alternative_conditions=alternatives,
    )


def _is_fraud_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute involves fraud."""
    # Fraud type code reported
    if case.fraud_type_code is not None:
        return True
    # Cardholder denies authorization/participation
    statement = (case.cardholder.cardholder_statement or "").lower()
    fraud_indicators = [
        "unauthorized",
        "fraud",
        "did not authorize",
        "did not make",
        "stolen",
        "lost",
        "counterfeit",
        "not mine",
        "identity theft",
    ]
    return any(indicator in statement for indicator in fraud_indicators)


def _is_authorization_dispute(case: DisputeCase) -> bool:
    """Determine if the dispute involves authorization issues."""
    txn = case.transaction
    # Declined authorization
    if txn.authorization_response_code and not txn.authorization_response_code.startswith("0"):
        return True
    # No authorization code present
    if txn.authorization_code is None:
        return True
    statement = (case.cardholder.cardholder_statement or "").lower()
    auth_indicators = [
        "declined",
        "no authorization",
        "over limit",
        "expired card",
        "card recovery",
        "late presentment",
    ]
    return any(indicator in statement for indicator in auth_indicators)


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
