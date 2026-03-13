"""Enumerations for the Visa disputes processing system."""

from __future__ import annotations

from enum import StrEnum


class DisputeCategory(StrEnum):
    """Visa dispute categories (Chapter 11)."""

    FRAUD = "10"
    AUTHORIZATION = "11"
    PROCESSING_ERRORS = "12"
    CONSUMER_DISPUTES = "13"


class DisputeCondition(StrEnum):
    """Specific dispute conditions within each category.

    Naming: category_condition, e.g. FRAUD_EMV_COUNTERFEIT = "10.1"
    """

    # Category 10: Fraud
    FRAUD_EMV_COUNTERFEIT = "10.1"
    FRAUD_EMV_NON_COUNTERFEIT = "10.2"
    FRAUD_CARD_PRESENT = "10.3"
    FRAUD_CARD_ABSENT = "10.4"
    FRAUD_VFMP = "10.5"

    # Category 11: Authorization
    AUTH_CARD_RECOVERY = "11.1"
    AUTH_DECLINED = "11.2"
    AUTH_NO_AUTH_LATE = "11.3"

    # Category 12: Processing Errors
    PROC_INCORRECT_CODE = "12.2"
    PROC_INCORRECT_CURRENCY = "12.3"
    PROC_INCORRECT_ACCOUNT = "12.4"
    PROC_INCORRECT_AMOUNT = "12.5"
    PROC_DUPLICATE = "12.6"
    PROC_INVALID_DATA = "12.7"

    # Category 13: Consumer Disputes
    CONSUMER_NOT_RECEIVED = "13.1"
    CONSUMER_CANCELLED_RECURRING = "13.2"
    CONSUMER_NOT_AS_DESCRIBED = "13.3"
    CONSUMER_COUNTERFEIT_MERCH = "13.4"
    CONSUMER_MISREPRESENTATION = "13.5"
    CONSUMER_CREDIT_NOT_PROCESSED = "13.6"
    CONSUMER_CANCELLED = "13.7"
    CONSUMER_OCT_NOT_ACCEPTED = "13.8"
    CONSUMER_ATM_NON_RECEIPT = "13.9"

    @property
    def category(self) -> DisputeCategory:
        cat = self.value.split(".")[0]
        return DisputeCategory(cat)


class DisputePhase(StrEnum):
    """Current phase in the dispute lifecycle."""

    INTAKE = "intake"
    DISPUTE_FILED = "dispute_filed"
    DISPUTE_RESPONSE = "dispute_response"  # Cat 12/13 only
    PRE_ARBITRATION_ATTEMPT = "pre_arbitration_attempt"
    PRE_ARBITRATION_RESPONSE = "pre_arbitration_response"
    ARBITRATION = "arbitration"
    COMPLIANCE = "compliance"
    RESOLVED = "resolved"


class DisputeStatus(StrEnum):
    """Overall status of a dispute case."""

    PENDING_REVIEW = "pending_review"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    FILED = "filed"
    AWAITING_RESPONSE = "awaiting_response"
    IN_PRE_ARBITRATION = "in_pre_arbitration"
    IN_ARBITRATION = "in_arbitration"
    IN_COMPLIANCE = "in_compliance"
    RESOLVED_ISSUER_WIN = "resolved_issuer_win"
    RESOLVED_ACQUIRER_WIN = "resolved_acquirer_win"
    RESOLVED_SPLIT = "resolved_split"
    CLOSED = "closed"


class TaskType(StrEnum):
    """Types of tasks the orchestrator can dispatch."""

    EVALUATE_ELIGIBILITY = "evaluate_eligibility"
    VALIDATE_DOCUMENTATION = "validate_documentation"
    CALCULATE_DEADLINE = "calculate_deadline"
    CHECK_INVALID_CONDITIONS = "check_invalid_conditions"
    DETERMINE_DISPUTE_CONDITION = "determine_dispute_condition"
    FILE_DISPUTE = "file_dispute"
    EVALUATE_RESPONSE = "evaluate_response"
    PREPARE_PRE_ARBITRATION = "prepare_pre_arbitration"
    EVALUATE_PRE_ARBITRATION = "evaluate_pre_arbitration"
    PREPARE_ARBITRATION = "prepare_arbitration"
    PREPARE_COMPLIANCE = "prepare_compliance"
    CALCULATE_DISPUTE_AMOUNT = "calculate_dispute_amount"
    REVIEW_COMPELLING_EVIDENCE = "review_compelling_evidence"


class TaskStatus(StrEnum):
    """Status of a processing task."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class PartyRole(StrEnum):
    """Roles in the dispute process."""

    ISSUER = "issuer"
    ACQUIRER = "acquirer"
    CARDHOLDER = "cardholder"
    MERCHANT = "merchant"


class TransactionEnvironment(StrEnum):
    """Transaction environment classification."""

    CARD_PRESENT = "card_present"
    CARD_ABSENT = "card_absent"
    ATM = "atm"
    ECOMMERCE = "ecommerce"
    MAIL_PHONE = "mail_phone"
    RECURRING = "recurring"


class FraudType(StrEnum):
    """Visa fraud activity type codes."""

    LOST = "0"
    STOLEN = "1"
    NOT_RECEIVED_AS_ISSUED = "2"
    FRAUDULENT_APPLICATION = "3"
    COUNTERFEIT = "4"
    ACCOUNT_TAKEOVER = "5"
    CARD_ABSENT = "7"
    MERCHANT_MISREPRESENTATION = "C"
    MANIPULATION = "D"


class Region(StrEnum):
    """Visa operating regions."""

    US = "US"
    CANADA = "CA"
    LAC = "LAC"
    EUROPE = "EU"
    CEMEA = "CEMEA"
    AP = "AP"
    INTERREGIONAL = "INTERREGIONAL"
    GLOBAL = "GLOBAL"
