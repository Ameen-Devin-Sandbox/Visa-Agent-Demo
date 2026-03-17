# THIS FILE IS AUTO-GENERATED from rules/generated/time_limits.yaml
# DO NOT EDIT MANUALLY. Run `python scripts/generate_rules.py` to regenerate.
# Source: Visa Core Rules V1.1 - 18 October 2025
"""Time limit calculations for Visa dispute conditions.

Encodes the specific time limits from Visa Core Rules Section 11 for each
dispute condition, including regional exceptions.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.models.dispute import TimeLimit
from src.models.enums import DisputeCondition, Region

DateLike = date | datetime

# Load time limits from YAML at import time
_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "rules" / "generated" / "time_limits.yaml"
with open(_YAML_PATH, encoding="utf-8") as _f:
    _TL_DATA: dict[str, Any] = yaml.safe_load(_f)


def _build_dispute_time_limits() -> dict[DisputeCondition, TimeLimit]:
    """Build the DISPUTE_TIME_LIMITS dict from YAML data."""
    result: dict[DisputeCondition, TimeLimit] = {}
    for cond_code, tl_data in _TL_DATA.get("dispute_time_limits", {}).items():
        try:
            condition = DisputeCondition(cond_code)
        except ValueError:
            continue
        result[condition] = TimeLimit(
            calendar_days=tl_data["calendar_days"],
            from_event=tl_data["from_event"],
            region_exceptions=tl_data.get("region_exceptions", {}),
            description=tl_data["description"],
        )
    return result


def _build_pre_arbitration_time_limits() -> dict[str, TimeLimit]:
    """Build the PRE_ARBITRATION_TIME_LIMITS dict from YAML data."""
    result: dict[str, TimeLimit] = {}
    for flow_name, tl_data in _TL_DATA.get("pre_arbitration_time_limits", {}).items():
        result[flow_name] = TimeLimit(
            calendar_days=tl_data["calendar_days"],
            from_event=tl_data["from_event"],
            region_exceptions=tl_data.get("region_exceptions", {}),
            description=tl_data["description"],
        )
    return result


def _build_arbitration_time_limit() -> TimeLimit:
    """Build the ARBITRATION_TIME_LIMIT from YAML data."""
    arb = _TL_DATA["arbitration_time_limit"]
    return TimeLimit(
        calendar_days=arb["calendar_days"],
        from_event=arb["from_event"],
        description=arb["description"],
    )


# Time limits encoded from Visa Core Rules Section 11
DISPUTE_TIME_LIMITS = _build_dispute_time_limits()

# Pre-arbitration time limits by dispute category flow
PRE_ARBITRATION_TIME_LIMITS = _build_pre_arbitration_time_limits()

# Arbitration time limit (same for all categories)
ARBITRATION_TIME_LIMIT = _build_arbitration_time_limit()


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
