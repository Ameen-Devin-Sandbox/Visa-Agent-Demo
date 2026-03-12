"""Core domain models for the Visa disputes processing system."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from visa_disputes_agent.models.enums import (
    DecisionOutcome,
    DisputeCategory,
    DisputeCondition,
    DisputeTaskStatus,
    DisputeWorkflowState,
    MemberRole,
    Priority,
    Region,
    TransactionEnvironment,
)


class Transaction(BaseModel):
    """Represents a Visa transaction involved in a dispute."""

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
    service_code: str = ""
    has_full_chip_data: bool = False
    is_visa_secure: bool = False
    region: Region = Region.ALL


class CardholderInfo(BaseModel):
    """Information about the cardholder filing the dispute."""

    cardholder_id: str = ""
    account_status: str = ""
    card_type: str = ""
    is_chip_card: bool = False
    has_signed_letter: bool = False
    letter_contents: str = ""
    attempted_merchant_resolution: bool = False
    financial_loss_confirmed: bool = False


class EvidenceItem(BaseModel):
    """A piece of evidence submitted with a dispute."""

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    evidence_type: str
    description: str
    document_reference: str = ""
    is_compelling: bool = False
    submitted_date: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DisputeTask(BaseModel):
    """A dispute task to be processed by the brain.

    This is the primary unit of work that flows through the system.
    """

    task_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: DisputeTaskStatus = DisputeTaskStatus.PENDING
    priority: Priority = Priority.MEDIUM
    workflow_state: DisputeWorkflowState = DisputeWorkflowState.INTAKE

    # Core dispute information
    dispute_category: DisputeCategory | None = None
    dispute_condition: DisputeCondition | None = None
    member_role: MemberRole = MemberRole.ISSUER
    region: Region = Region.ALL

    # Transaction details
    transaction: Transaction
    cardholder: CardholderInfo = Field(default_factory=CardholderInfo)

    # Evidence and documentation
    evidence: list[EvidenceItem] = Field(default_factory=list)
    issuer_certification: str = ""
    has_cardholder_letter: bool = False

    # Processing metadata
    dispute_amount: Decimal = Decimal("0")
    dispute_reason: str = ""
    dispute_filing_date: date | None = None

    # Tracking
    assigned_agent: str = ""
    processing_log: list[ProcessingLogEntry] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3

    def add_log_entry(self, action: str, details: str, agent: str = "") -> None:
        """Add a processing log entry."""
        entry = ProcessingLogEntry(
            action=action,
            details=details,
            agent=agent or self.assigned_agent,
        )
        self.processing_log.append(entry)
        self.updated_at = datetime.utcnow()


class ProcessingLogEntry(BaseModel):
    """A log entry tracking processing actions on a dispute."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str
    details: str
    agent: str = ""


class RuleEvaluationResult(BaseModel):
    """Result of evaluating a specific Visa rule against a dispute."""

    rule_id: str
    rule_section: str
    rule_description: str
    is_satisfied: bool
    details: str
    applicable_region: Region = Region.ALL
    evidence_required: list[str] = Field(default_factory=list)
    evidence_provided: list[str] = Field(default_factory=list)


class TimeLimitResult(BaseModel):
    """Result of checking dispute time limits."""

    is_within_time_limit: bool
    time_limit_days: int
    start_date: date
    deadline_date: date
    days_remaining: int
    rule_reference: str
    notes: str = ""


class DisputeDecision(BaseModel):
    """The final decision output from processing a dispute.

    This is the primary output of the brain for each dispute task.
    """

    decision_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    decided_at: datetime = Field(default_factory=datetime.utcnow)

    # Decision
    outcome: DecisionOutcome
    confidence_score: float = Field(ge=0.0, le=1.0)
    dispute_amount_approved: Decimal = Decimal("0")

    # Reasoning
    reasoning: str
    applicable_rules: list[RuleEvaluationResult] = Field(default_factory=list)
    time_limit_check: TimeLimitResult | None = None

    # Response
    response_code: str = ""
    response_message: str = ""
    required_actions: list[str] = Field(default_factory=list)
    compelling_evidence_needed: list[str] = Field(default_factory=list)

    # Escalation
    escalation_reason: str = ""
    human_review_notes: str = ""

    def is_final(self) -> bool:
        """Check if this is a final decision (no further action needed)."""
        return self.outcome in {
            DecisionOutcome.DISPUTE_VALID,
            DecisionOutcome.DISPUTE_INVALID,
            DecisionOutcome.DISPUTE_PARTIALLY_VALID,
        }
