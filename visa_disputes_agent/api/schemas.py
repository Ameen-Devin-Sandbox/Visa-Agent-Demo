"""API request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from visa_disputes_agent.models.enums import (
    DecisionOutcome,
    DisputeCategory,
    DisputeCondition,
    DisputeTaskStatus,
    MemberRole,
    Priority,
    Region,
    TransactionEnvironment,
)


class TransactionRequest(BaseModel):
    """Transaction data for a dispute submission."""

    transaction_id: str
    transaction_date: date
    processing_date: date
    amount: Decimal
    currency: str = "USD"
    merchant_name: str
    merchant_category_code: str
    merchant_country: str = ""
    acquirer_bin: str = ""
    issuer_bin: str = ""
    card_number_masked: str = ""
    environment: TransactionEnvironment = TransactionEnvironment.CARD_PRESENT
    is_chip_transaction: bool = False
    is_chip_reading_device: bool = False
    is_contactless: bool = False
    is_recurring: bool = False
    is_ecommerce: bool = False
    authorization_code: str = ""
    authorization_response_code: str = ""
    was_authorized: bool = True
    pos_entry_mode: str = ""
    has_full_chip_data: bool = False
    is_visa_secure: bool = False
    region: Region = Region.ALL


class CardholderInfoRequest(BaseModel):
    """Cardholder information for a dispute submission."""

    cardholder_id: str = ""
    account_status: str = ""
    card_type: str = ""
    is_chip_card: bool = False
    has_signed_letter: bool = False
    attempted_merchant_resolution: bool = False
    financial_loss_confirmed: bool = False


class EvidenceRequest(BaseModel):
    """Evidence item for a dispute submission."""

    evidence_type: str
    description: str
    document_reference: str = ""
    is_compelling: bool = False


class SubmitDisputeRequest(BaseModel):
    """Request to submit a new dispute for processing."""

    dispute_category: DisputeCategory | None = None
    dispute_condition: DisputeCondition | None = None
    member_role: MemberRole = MemberRole.ISSUER
    region: Region = Region.ALL
    priority: Priority = Priority.MEDIUM

    transaction: TransactionRequest
    cardholder: CardholderInfoRequest = Field(default_factory=CardholderInfoRequest)

    evidence: list[EvidenceRequest] = Field(default_factory=list)
    issuer_certification: str = ""
    has_cardholder_letter: bool = False

    dispute_amount: Decimal
    dispute_reason: str = ""
    dispute_filing_date: date | None = None


class SubmitDisputeResponse(BaseModel):
    """Response after submitting a dispute."""

    task_id: UUID
    status: DisputeTaskStatus
    message: str


class DisputeStatusResponse(BaseModel):
    """Response for a dispute status query."""

    task_id: UUID
    status: DisputeTaskStatus | None
    decision: DecisionResponse | None = None


class RuleEvalResponse(BaseModel):
    """A rule evaluation result in the response."""

    rule_id: str
    rule_section: str
    rule_description: str
    is_satisfied: bool
    details: str


class TimeLimitResponse(BaseModel):
    """Time limit check result in the response."""

    is_within_time_limit: bool
    time_limit_days: int
    start_date: date
    deadline_date: date
    days_remaining: int
    rule_reference: str


class DecisionResponse(BaseModel):
    """Response containing a dispute decision."""

    decision_id: UUID
    task_id: UUID
    decided_at: datetime
    outcome: DecisionOutcome
    confidence_score: float
    dispute_amount_approved: Decimal
    reasoning: str
    applicable_rules: list[RuleEvalResponse] = Field(default_factory=list)
    time_limit_check: TimeLimitResponse | None = None
    response_code: str = ""
    response_message: str = ""
    required_actions: list[str] = Field(default_factory=list)
    escalation_reason: str = ""
    human_review_notes: str = ""


class QueueStatsResponse(BaseModel):
    """Response containing queue and brain statistics."""

    queue: dict[str, int] = Field(default_factory=dict)
    decisions: dict[str, object] = Field(default_factory=dict)
    is_running: bool = False
    agents: list[dict[str, str]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    brain_running: bool
    queue_pending: int
    queue_in_progress: int
    total_decisions: int
