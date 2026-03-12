"""Enumerations for the Visa disputes processing system."""

from enum import StrEnum


class DisputeCategory(StrEnum):
    """Visa dispute categories as defined in Section 11.6."""

    FRAUD = "10"
    AUTHORIZATION = "11"
    PROCESSING_ERRORS = "12"
    CONSUMER_DISPUTES = "13"


class DisputeCondition(StrEnum):
    """Specific dispute conditions within each category."""

    # Category 10: Fraud
    EMV_LIABILITY_SHIFT_COUNTERFEIT = "10.1"
    EMV_LIABILITY_SHIFT_NON_COUNTERFEIT = "10.2"
    OTHER_FRAUD_CARD_PRESENT = "10.3"
    OTHER_FRAUD_CARD_ABSENT = "10.4"
    VISA_FRAUD_MONITORING_PROGRAM = "10.5"

    # Category 11: Authorization
    CARD_RECOVERY_BULLETIN = "11.1"
    DECLINED_AUTHORIZATION = "11.2"
    NO_AUTHORIZATION_LATE_PRESENTMENT = "11.3"

    # Category 12: Processing Errors
    INCORRECT_TRANSACTION_CODE = "12.1"
    INCORRECT_AMOUNT = "12.2"
    INCORRECT_ACCOUNT_NUMBER = "12.3"
    INCORRECT_ACCOUNT_NUMBER_CROSS_BORDER = "12.4"
    DUPLICATE_PROCESSING = "12.5"
    PAID_BY_OTHER_MEANS = "12.6"
    INVALID_DATA = "12.7"
    LATE_PRESENTMENT = "12.8"
    INCORRECT_CURRENCY = "12.9"

    # Category 13: Consumer Disputes
    MERCHANDISE_SERVICES_NOT_RECEIVED = "13.1"
    MERCHANDISE_NOT_AS_DESCRIBED = "13.2"
    COUNTERFEIT_MERCHANDISE = "13.3"
    MISREPRESENTATION = "13.4"
    DEFECTIVE_MERCHANDISE = "13.5"
    CANCELLED_RECURRING = "13.6"
    CANCELLED_MERCHANDISE_SERVICES = "13.7"
    ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED = "13.8"
    NON_RECEIPT_OF_CASH_ATM = "13.9"


class DisputeTaskStatus(StrEnum):
    """Status of a dispute task in the processing queue."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class DisputeWorkflowState(StrEnum):
    """States in the dispute processing workflow state machine."""

    INTAKE = "intake"
    VALIDATION = "validation"
    CATEGORIZATION = "categorization"
    RULE_EVALUATION = "rule_evaluation"
    EVIDENCE_REVIEW = "evidence_review"
    TIME_LIMIT_CHECK = "time_limit_check"
    DECISION = "decision"
    RESPONSE_GENERATION = "response_generation"
    PRE_ARBITRATION = "pre_arbitration"
    ARBITRATION = "arbitration"
    RESOLUTION = "resolution"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class TransactionEnvironment(StrEnum):
    """Transaction environment classification."""

    CARD_PRESENT = "card_present"
    CARD_ABSENT = "card_absent"
    ATM = "atm"
    ECOMMERCE = "ecommerce"
    MAIL_PHONE = "mail_phone"
    RECURRING = "recurring"


class Region(StrEnum):
    """Visa regions for rule applicability."""

    ALL = "all"
    AP = "ap"
    CANADA = "canada"
    CEMEA = "cemea"
    EUROPE = "europe"
    LAC = "lac"
    US = "us"


class DecisionOutcome(StrEnum):
    """Possible outcomes of dispute processing."""

    DISPUTE_VALID = "dispute_valid"
    DISPUTE_INVALID = "dispute_invalid"
    DISPUTE_PARTIALLY_VALID = "dispute_partially_valid"
    REQUIRES_COMPELLING_EVIDENCE = "requires_compelling_evidence"
    ESCALATE_TO_PRE_ARBITRATION = "escalate_to_pre_arbitration"
    ESCALATE_TO_ARBITRATION = "escalate_to_arbitration"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    INSUFFICIENT_DOCUMENTATION = "insufficient_documentation"


class Priority(StrEnum):
    """Task priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MemberRole(StrEnum):
    """Role of the member in the dispute."""

    ISSUER = "issuer"
    ACQUIRER = "acquirer"
