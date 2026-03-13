"""Rule data models — the structured encoding of Visa dispute rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.enums import DisputeCondition, Region, TransactionEnvironment


@dataclass
class TimeLimitRule:
    """Time limit for a dispute action."""

    calendar_days: int
    from_event: str  # e.g. "transaction_processing_date", "dispute_processing_date"
    wait_days_before: int = 0  # e.g. 15 days before filing for 13.1
    max_calendar_days: int | None = None  # e.g. 540 days absolute cap
    description: str = ""
    regional_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class InvalidCondition:
    """A condition under which a dispute is invalid and cannot be filed."""

    condition_id: str
    description: str
    check_field: str | None = None  # Field on TransactionDetail to check
    check_value: str | None = None
    check_logic: str = "equals"  # "equals", "greater_than", "contains", "custom"
    region: Region | None = None  # None = applies globally
    effective_date: str | None = None  # "YYYY-MM-DD" if not yet effective


@dataclass
class DocumentRequirement:
    """Required documentation for a dispute condition."""

    requirement_id: str
    description: str
    document_type: str
    required_by: str = "issuer"  # "issuer" or "acquirer"
    is_mandatory: bool = True
    condition_notes: str = ""


@dataclass
class CompellingEvidenceItem:
    """A type of compelling evidence per Table 11-6."""

    item_number: int
    description: str
    applicable_conditions: list[DisputeCondition]
    sub_requirements: list[str] = field(default_factory=list)


@dataclass
class PreArbitrationRight:
    """Rights for pre-arbitration attempt or response."""

    description: str
    actor: str  # "issuer" or "acquirer"
    evidence_types: list[str] = field(default_factory=list)
    regional_notes: dict[str, str] = field(default_factory=dict)


@dataclass
class DisputeConditionRule:
    """Complete encoded rule for a single dispute condition."""

    condition: DisputeCondition
    name: str
    description: str
    triggers: list[str]
    prerequisites: list[str]
    time_limit: TimeLimitRule
    dispute_amount_rule: str  # Human-readable rule for calculating amount
    invalid_conditions: list[InvalidCondition]
    documentation_requirements: list[DocumentRequirement]
    pre_arbitration_rights: list[PreArbitrationRight]
    dispute_response_rights: list[str] | None = None  # Only for Cat 12/13
    environments: list[TransactionEnvironment] = field(default_factory=list)
    special_notes: list[str] = field(default_factory=list)
    rule_section: str = ""  # e.g. "11.7.2"


@dataclass
class ProcessFlowRule:
    """Dispute resolution process flow for a category group."""

    applicable_categories: list[str]  # ["10", "11"] or ["12", "13"]
    stages: list[ProcessStage]


@dataclass
class ProcessStage:
    """A single stage in the dispute resolution process."""

    name: str
    actor: str  # "issuer" or "acquirer"
    time_limit: TimeLimitRule
    description: str
    financial_message: str | None = None
    regional_overrides: dict[str, str] = field(default_factory=dict)
