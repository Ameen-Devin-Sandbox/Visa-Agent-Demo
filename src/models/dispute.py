"""Core dispute and transaction data models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    DisputePhase,
    DisputeStatus,
    FraudType,
    PartyRole,
    Region,
    TransactionEnvironment,
)


class Party(BaseModel):
    """A party involved in the dispute (issuer, acquirer, cardholder, merchant)."""

    role: PartyRole
    name: str
    institution_id: str | None = None
    region: Region = Region.US
    country_code: str = "US"


class TransactionDetail(BaseModel):
    """Details about the original transaction being disputed."""

    transaction_id: str
    acquirer_reference_number: str | None = None
    transaction_date: date
    processing_date: date
    amount: Decimal
    currency: str = "USD"
    billing_amount: Decimal | None = None
    billing_currency: str | None = None
    merchant_name: str
    merchant_category_code: str
    merchant_country: str = "US"
    environment: TransactionEnvironment = TransactionEnvironment.CARD_PRESENT
    is_chip_initiated: bool = False
    is_chip_reading_device: bool = False
    is_contactless: bool = False
    is_recurring: bool = False
    is_installment: bool = False
    pos_entry_mode: str | None = None
    eci_indicator: str | None = None  # 5 = Secure e-commerce, 6 = Non-authenticated
    cavv_present: bool = False
    tavv_present: bool = False
    cvv2_result: str | None = None  # N, U, Y, etc.
    cvv2_presence_indicator: str | None = None
    avs_result: str | None = None  # Y, N, U, etc.
    three_ds_authenticated: bool = False
    full_chip_data_transmitted: bool = False
    electronic_imprint: bool = False
    authorization_code: str | None = None
    authorization_response: str | None = None  # Approval, Decline code, etc.
    is_token_transaction: bool = False
    is_mobile_push_payment: bool = False
    is_straight_through_processing: bool = False
    is_emergency_cash: bool = False
    delayed_charge_indicator: str | None = None
    fraud_type_reported: FraudType | None = None
    is_dcc: bool = False  # Dynamic currency conversion


class DocumentEvidence(BaseModel):
    """Documentation or evidence attached to a dispute."""

    document_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    document_type: str  # e.g. "cardholder_certification", "transaction_receipt", etc.
    description: str
    provided_by: PartyRole
    provided_date: date
    content_summary: str | None = None
    is_in_english: bool = True


class DisputeAction(BaseModel):
    """An action taken during the dispute lifecycle."""

    action_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    phase: DisputePhase
    actor: PartyRole
    action_type: str  # "filed", "responded", "accepted", "declined", "escalated"
    processing_date: date
    amount: Decimal | None = None
    currency: str | None = None
    description: str
    evidence: list[DocumentEvidence] = Field(default_factory=list)
    deadline: date | None = None


class Dispute(BaseModel):
    """A complete dispute case."""

    dispute_id: UUID = Field(default_factory=uuid4)
    transaction: TransactionDetail
    category: DisputeCategory | None = None
    condition: DisputeCondition | None = None
    phase: DisputePhase = DisputePhase.INTAKE
    status: DisputeStatus = DisputeStatus.PENDING_REVIEW
    dispute_amount: Decimal | None = None
    dispute_currency: str = "USD"
    issuer: Party
    acquirer: Party
    cardholder: Party
    merchant: Party
    actions: list[DisputeAction] = Field(default_factory=list)
    evidence: list[DocumentEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolution_summary: str | None = None
    is_rapid_dispute_resolution: bool = False

    # Fraud-specific
    fraud_reported_to_visa: bool = False
    fraud_type: FraudType | None = None

    # Tracking
    prior_credits_applied: list[str] = Field(default_factory=list)
    cardholder_financial_loss: bool = True
    cardholder_attempted_resolution: bool = False
    disputes_on_account_last_120_days: int = 0

    @property
    def is_fraud_category(self) -> bool:
        return self.category == DisputeCategory.FRAUD

    @property
    def is_authorization_category(self) -> bool:
        return self.category == DisputeCategory.AUTHORIZATION

    @property
    def uses_dispute_response_flow(self) -> bool:
        """Categories 12/13 have a Dispute Response stage; 10/11 do not."""
        return self.category in (
            DisputeCategory.PROCESSING_ERRORS,
            DisputeCategory.CONSUMER_DISPUTES,
        )

    @property
    def last_processing_date(self) -> date | None:
        if self.actions:
            return self.actions[-1].processing_date
        return None
