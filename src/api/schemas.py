"""API request/response schemas."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from src.models.enums import (
    FraudTypeCode,
    Region,
    TaskPriority,
    TransactionEnvironment,
)


class TransactionRequest(BaseModel):
    """Request schema for transaction details."""

    transaction_id: str
    acquirer_reference_number: str | None = None
    transaction_date: date
    processing_date: date
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    merchant_name: str
    merchant_category_code: str = "5411"
    merchant_country: str = "US"
    acquirer_bin: str = "000000"
    issuer_bin: str = "000000"
    environment: TransactionEnvironment = TransactionEnvironment.ECOMMERCE
    is_chip_card: bool = False
    is_chip_initiated: bool = False
    is_contactless: bool = False
    is_token_transaction: bool = False
    is_recurring: bool = False
    pos_entry_mode: str | None = None
    terminal_entry_capability: str | None = None
    cvv_present: bool = False
    cvv_verified: bool | None = None
    avs_result_code: str | None = None
    three_d_secure_authenticated: bool = False
    authorization_code: str | None = None
    authorization_response_code: str | None = None
    full_chip_data_transmitted: bool = False
    is_fallback_transaction: bool = False
    is_delayed_charge: bool = False
    is_mobile_push_payment: bool = False
    is_emergency_cash_disbursement: bool = False
    is_veps_transaction: bool = False
    region: Region = Region.US


class CardholderRequest(BaseModel):
    """Request schema for cardholder information."""

    cardholder_name: str
    partial_payment_credential: str
    contact_email: str | None = None
    contact_phone: str | None = None
    cardholder_statement: str | None = None
    signed_letter_provided: bool = False


class EvidenceRequest(BaseModel):
    """Request schema for submitting evidence."""

    description: str
    evidence_type: str
    provided_by: str = "issuer"
    is_compelling_evidence: bool = False
    document_references: list[str] = Field(default_factory=list)


class DisputeSubmitRequest(BaseModel):
    """Request schema for submitting a new dispute."""

    transaction: TransactionRequest
    cardholder: CardholderRequest
    fraud_type_code: FraudTypeCode | None = None
    evidence: list[EvidenceRequest] = Field(default_factory=list)
    issuer_certification: str | None = None
    dispute_amount: float | None = None
    dispute_currency: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM


class HumanReviewRequest(BaseModel):
    """Request schema for human review decisions."""

    approved: bool
    reviewer_notes: str = ""


class EscalationRequest(BaseModel):
    """Request schema for escalating a dispute."""

    acquirer_evidence: list[EvidenceRequest] = Field(default_factory=list)


class DisputeSummaryResponse(BaseModel):
    """Response schema for dispute case summary."""

    case_id: str
    stage: str
    category: str | None = None
    condition: str | None = None
    resolution: str | None = None
    confidence: float | None = None
    requires_human_review: bool | None = None
    assigned_agent: str | None = None
    rule_evaluations_count: int = 0
    evidence_count: int = 0
    processing_notes_count: int = 0
    created_at: str
    updated_at: str


class DisputeDetailResponse(BaseModel):
    """Response schema for detailed dispute information."""

    case_id: str
    stage: str
    category: str | None = None
    condition: str | None = None

    # Transaction
    transaction_id: str
    transaction_amount: float
    transaction_currency: str
    merchant_name: str
    transaction_environment: str

    # Decision
    resolution: str | None = None
    rationale: str | None = None
    confidence: float | None = None
    requires_human_review: bool = False
    decided_by: str | None = None

    # Rule evaluations
    rule_evaluations: list[dict[str, Any]] = Field(default_factory=list)

    # Evidence
    evidence: list[dict[str, Any]] = Field(default_factory=list)

    # Processing
    processing_notes: list[str] = Field(default_factory=list)
    stage_history: list[dict[str, str]] = Field(default_factory=list)

    # Timestamps
    created_at: str
    updated_at: str


class QueueStatsResponse(BaseModel):
    """Response schema for queue statistics."""

    queue_depth: dict[str, int]
    stats: dict[str, int]


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str
    version: str
    agents_loaded: int
    queue_depth: int
