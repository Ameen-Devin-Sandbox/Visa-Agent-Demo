"""Time limit calculations for Visa dispute conditions.

Encodes the specific time limits from Visa Core Rules Section 11 for each
dispute condition, including regional exceptions.
"""

from datetime import date, datetime, timedelta

from src.models.dispute import TimeLimit
from src.models.enums import DisputeCondition, Region

DateLike = date | datetime

# Time limits encoded from Visa Core Rules Section 11
# Each condition has a base time limit and optional regional exceptions
DISPUTE_TIME_LIMITS: dict[DisputeCondition, TimeLimit] = {
    # Category 10: Fraud
    DisputeCondition.EMV_COUNTERFEIT_FRAUD: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.OTHER_FRAUD_CARD_PRESENT: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.OTHER_FRAUD_CARD_ABSENT: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.VISA_FRAUD_MONITORING: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    # Category 11: Authorization
    DisputeCondition.CARD_RECOVERY_BULLETIN: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.DECLINED_AUTHORIZATION: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.NO_AUTHORIZATION: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    # Category 12: Processing Errors
    DisputeCondition.INCORRECT_TRANSACTION_CODE: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.INCORRECT_CURRENCY: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.INCORRECT_ACCOUNT_NUMBER: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.INCORRECT_AMOUNT: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.DUPLICATE_PROCESSING: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.INVALID_DATA: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    # Category 13: Consumer Disputes
    DisputeCondition.MERCHANDISE_NOT_RECEIVED: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        region_exceptions={
            "europe_ecommerce": 540,  # Extended for digital goods in Europe
        },
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.CANCELLED_RECURRING: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.NOT_AS_DESCRIBED: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.COUNTERFEIT_MERCHANDISE: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.MISREPRESENTATION: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.CREDIT_NOT_PROCESSED: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.CANCELLED_MERCHANDISE: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.OCT_NOT_ACCEPTED: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
    DisputeCondition.NON_RECEIPT_CASH_ATM: TimeLimit(
        calendar_days=120,
        from_event="transaction_processing_date",
        description="120 calendar days from the Transaction Processing Date",
    ),
}

# Pre-arbitration time limits by dispute category flow
PRE_ARBITRATION_TIME_LIMITS: dict[str, TimeLimit] = {
    "category_10_11": TimeLimit(
        calendar_days=30,
        from_event="dispute_processing_date",
        region_exceptions={
            "cemea_nigeria": 2,  # 2 business days for domestic
            "europe_poland_atm": 20,
            "cemea_tanzania": 20,
        },
        description="30 calendar days from the Dispute Processing Date",
    ),
    "category_12_13_response": TimeLimit(
        calendar_days=30,
        from_event="dispute_processing_date",
        region_exceptions={
            "cemea_egypt_atm": 10,
            "ap_india_atm": 6,
            "cemea_nigeria": 2,
            "europe_poland_atm": 20,
            "cemea_tanzania": 20,
        },
        description="30 calendar days from the Dispute Processing Date",
    ),
    "category_12_13_pre_arb": TimeLimit(
        calendar_days=30,
        from_event="dispute_response_processing_date",
        region_exceptions={
            "cemea_tanzania": 10,
        },
        description="30 calendar days from the Dispute Response Processing Date",
    ),
}

# Arbitration time limit (same for all categories)
ARBITRATION_TIME_LIMIT = TimeLimit(
    calendar_days=10,
    from_event="pre_arbitration_response_processing_date",
    description="10 calendar days from the Processing Date of the pre-Arbitration response",
)


def calculate_deadline(
    event_date: DateLike,
    condition: DisputeCondition,
    region: Region = Region.GLOBAL,
) -> DateLike:
    """Calculate the deadline for filing a dispute.

    Per Section 11.2.1: For the purpose of calculating a dispute-related
    timeframe, the Processing Date of the preceding event is not counted
    as one day.
    """
    time_limit = DISPUTE_TIME_LIMITS.get(condition)
    if time_limit is None:
        raise ValueError(f"No time limit defined for condition {condition.value}")

    days = time_limit.calendar_days
    # The processing date itself is NOT counted (per 11.2.1)
    return event_date + timedelta(days=days + 1)


def _to_date(d: DateLike) -> date:
    """Normalize a date or datetime to a plain date for comparison."""
    if isinstance(d, datetime):
        return d.date()
    return d


def is_within_time_limit(
    event_date: DateLike,
    filing_date: DateLike,
    condition: DisputeCondition,
    region: Region = Region.GLOBAL,
) -> bool:
    """Check if a dispute filing is within the allowed time limit."""
    deadline = calculate_deadline(event_date, condition, region)
    return _to_date(filing_date) <= _to_date(deadline)


def get_pre_arbitration_deadline(
    preceding_event_date: datetime,
    category_flow: str,
    region: Region = Region.GLOBAL,
    is_atm: bool = False,
    is_domestic: bool = False,
    country: str | None = None,
) -> datetime:
    """Calculate the pre-arbitration deadline with regional exceptions.

    Args:
        preceding_event_date: The processing date of the preceding event.
        category_flow: Either "category_10_11" or "category_12_13_response"
                       or "category_12_13_pre_arb".
        region: The Visa region.
        is_atm: Whether this involves an ATM transaction.
        is_domestic: Whether this is a domestic transaction.
        country: Specific country for domestic exception lookups.
    """
    time_limit = PRE_ARBITRATION_TIME_LIMITS.get(category_flow)
    if time_limit is None:
        raise ValueError(f"No pre-arbitration time limit for flow: {category_flow}")

    days = time_limit.calendar_days

    # Apply regional exceptions
    if region == Region.CEMEA and is_domestic:
        if country == "nigeria":
            exception_key = "cemea_nigeria"
            if exception_key in time_limit.region_exceptions:
                days = time_limit.region_exceptions[exception_key]
        elif country == "tanzania":
            exception_key = "cemea_tanzania"
            if exception_key in time_limit.region_exceptions:
                days = time_limit.region_exceptions[exception_key]
        elif country == "egypt" and is_atm:
            exception_key = "cemea_egypt_atm"
            if exception_key in time_limit.region_exceptions:
                days = time_limit.region_exceptions[exception_key]

    if region == Region.EUROPE and country == "poland" and is_atm:
        exception_key = "europe_poland_atm"
        if exception_key in time_limit.region_exceptions:
            days = time_limit.region_exceptions[exception_key]

    if region == Region.AP and is_domestic and is_atm and country == "india":
        exception_key = "ap_india_atm"
        if exception_key in time_limit.region_exceptions:
            days = time_limit.region_exceptions[exception_key]

    return preceding_event_date + timedelta(days=days + 1)


def get_arbitration_deadline(pre_arb_response_date: datetime) -> datetime:
    """Calculate the arbitration filing deadline.

    10 calendar days from the Processing Date of the pre-Arbitration response.
    """
    return pre_arb_response_date + timedelta(days=ARBITRATION_TIME_LIMIT.calendar_days + 1)
