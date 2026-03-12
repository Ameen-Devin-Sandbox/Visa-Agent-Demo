"""Enumerations for the Visa Disputes Processing system."""

from enum import Enum, StrEnum


class DisputeCategory(StrEnum):
    """Visa dispute categories as defined in Section 11.6."""

    FRAUD = "10"
    AUTHORIZATION = "11"
    PROCESSING_ERRORS = "12"
    CONSUMER_DISPUTES = "13"


class DisputeCondition(StrEnum):
    """Specific dispute conditions within each category."""

    # Category 10: Fraud
    EMV_COUNTERFEIT_FRAUD = "10.1"
    EMV_NON_COUNTERFEIT_FRAUD = "10.2"
    OTHER_FRAUD_CARD_PRESENT = "10.3"
    OTHER_FRAUD_CARD_ABSENT = "10.4"
    VISA_FRAUD_MONITORING = "10.5"

    # Category 11: Authorization
    CARD_RECOVERY_BULLETIN = "11.1"
    DECLINED_AUTHORIZATION = "11.2"
    NO_AUTHORIZATION = "11.3"

    # Category 12: Processing Errors
    INCORRECT_TRANSACTION_CODE = "12.2"
    INCORRECT_CURRENCY = "12.3"
    INCORRECT_ACCOUNT_NUMBER = "12.4"
    INCORRECT_AMOUNT = "12.5"
    DUPLICATE_PROCESSING = "12.6"
    INVALID_DATA = "12.7"

    # Category 13: Consumer Disputes
    MERCHANDISE_NOT_RECEIVED = "13.1"
    CANCELLED_RECURRING = "13.2"
    NOT_AS_DESCRIBED = "13.3"
    COUNTERFEIT_MERCHANDISE = "13.4"
    MISREPRESENTATION = "13.5"
    CREDIT_NOT_PROCESSED = "13.6"
    CANCELLED_MERCHANDISE = "13.7"
    OCT_NOT_ACCEPTED = "13.8"
    NON_RECEIPT_CASH_ATM = "13.9"

    @property
    def category(self) -> DisputeCategory:
        """Return the parent category for this condition."""
        prefix = self.value.split(".")[0]
        return DisputeCategory(prefix)


class DisputeLifecycleStage(StrEnum):
    """Stages in the dispute lifecycle state machine."""

    INTAKE = "intake"
    VALIDATION = "validation"
    CATEGORIZATION = "categorization"
    RULE_EVALUATION = "rule_evaluation"
    PROCESSING = "processing"
    DECISION = "decision"
    PRE_ARBITRATION = "pre_arbitration"
    PRE_ARBITRATION_RESPONSE = "pre_arbitration_response"
    ARBITRATION = "arbitration"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    HUMAN_REVIEW = "human_review"
    FAILED = "failed"


class DisputeResolution(StrEnum):
    """Possible dispute resolutions."""

    ISSUER_WIN = "issuer_win"
    ACQUIRER_WIN = "acquirer_win"
    SPLIT_LIABILITY = "split_liability"
    WITHDRAWN = "withdrawn"
    ESCALATED_PRE_ARBITRATION = "escalated_pre_arbitration"
    ESCALATED_ARBITRATION = "escalated_arbitration"
    HUMAN_OVERRIDE = "human_override"
    INVALID_DISPUTE = "invalid_dispute"


class TransactionEnvironment(StrEnum):
    """Transaction environment classification."""

    CARD_PRESENT = "card_present"
    CARD_ABSENT = "card_absent"
    ATM = "atm"
    ECOMMERCE = "ecommerce"
    MOTO = "mail_order_telephone_order"


class FraudTypeCode(StrEnum):
    """Visa fraud type codes for reporting."""

    LOST = "0"
    STOLEN = "1"
    NOT_RECEIVED = "2"
    COUNTERFEIT = "4"
    ACCOUNT_TAKEOVER = "7"
    MERCHANT_MISREPRESENTATION = "C"
    MANIPULATION = "D"


class Region(StrEnum):
    """Visa operating regions."""

    AP = "ap"
    CEMEA = "cemea"
    EUROPE = "europe"
    LAC = "lac"
    US = "us"
    CANADA = "canada"
    GLOBAL = "global"


class TaskPriority(int, Enum):
    """Task priority levels (lower number = higher priority)."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class TaskStatus(StrEnum):
    """Task processing status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


class AgentType(StrEnum):
    """Types of specialized sub-agents."""

    FRAUD = "fraud_agent"
    AUTHORIZATION = "authorization_agent"
    PROCESSING_ERRORS = "processing_errors_agent"
    CONSUMER_DISPUTES = "consumer_disputes_agent"
    PRE_ARBITRATION = "pre_arbitration_agent"
    ARBITRATION = "arbitration_agent"
