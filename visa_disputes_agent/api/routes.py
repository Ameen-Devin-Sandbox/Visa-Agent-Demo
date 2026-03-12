"""FastAPI routes for the dispute processing API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from visa_disputes_agent.api.schemas import (
    DecisionResponse,
    DisputeStatusResponse,
    HealthResponse,
    QueueStatsResponse,
    RuleEvalResponse,
    SubmitDisputeRequest,
    SubmitDisputeResponse,
    TimeLimitResponse,
)
from visa_disputes_agent.models.dispute import (
    CardholderInfo,
    DisputeDecision,
    DisputeTask,
    EvidenceItem,
    Transaction,
)
from visa_disputes_agent.models.enums import DisputeTaskStatus
from visa_disputes_agent.orchestrator.brain import DisputeBrain

router = APIRouter()

# Brain instance - initialized in app startup
_brain: DisputeBrain | None = None


def set_brain(brain: DisputeBrain) -> None:
    """Set the brain instance for the API routes."""
    global _brain
    _brain = brain


def get_brain() -> DisputeBrain:
    """Get the brain instance, raising if not initialized."""
    if _brain is None:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    return _brain


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    brain = get_brain()
    stats = brain.get_stats()
    queue_stats = stats.get("queue", {})
    decision_stats = stats.get("decisions", {})

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        brain_running=brain.is_running,
        queue_pending=queue_stats.get("pending", 0) if isinstance(queue_stats, dict) else 0,
        queue_in_progress=queue_stats.get("in_progress", 0) if isinstance(queue_stats, dict) else 0,
        total_decisions=decision_stats.get("total", 0) if isinstance(decision_stats, dict) else 0,
    )


@router.post("/disputes", response_model=SubmitDisputeResponse, status_code=201)
async def submit_dispute(request: SubmitDisputeRequest) -> SubmitDisputeResponse:
    """Submit a new dispute for processing.

    The brain will pick up the dispute from the queue and process it
    according to Visa Core Rules.
    """
    brain = get_brain()

    # Convert request to domain model
    transaction = Transaction(
        transaction_id=request.transaction.transaction_id,
        transaction_date=request.transaction.transaction_date,
        processing_date=request.transaction.processing_date,
        amount=request.transaction.amount,
        currency=request.transaction.currency,
        merchant_name=request.transaction.merchant_name,
        merchant_category_code=request.transaction.merchant_category_code,
        merchant_country=request.transaction.merchant_country,
        acquirer_bin=request.transaction.acquirer_bin,
        issuer_bin=request.transaction.issuer_bin,
        card_number_masked=request.transaction.card_number_masked,
        environment=request.transaction.environment,
        is_chip_transaction=request.transaction.is_chip_transaction,
        is_chip_reading_device=request.transaction.is_chip_reading_device,
        is_contactless=request.transaction.is_contactless,
        is_recurring=request.transaction.is_recurring,
        is_ecommerce=request.transaction.is_ecommerce,
        authorization_code=request.transaction.authorization_code,
        authorization_response_code=request.transaction.authorization_response_code,
        was_authorized=request.transaction.was_authorized,
        pos_entry_mode=request.transaction.pos_entry_mode,
        has_full_chip_data=request.transaction.has_full_chip_data,
        is_visa_secure=request.transaction.is_visa_secure,
        region=request.transaction.region,
    )

    cardholder = CardholderInfo(
        cardholder_id=request.cardholder.cardholder_id,
        account_status=request.cardholder.account_status,
        card_type=request.cardholder.card_type,
        is_chip_card=request.cardholder.is_chip_card,
        has_signed_letter=request.cardholder.has_signed_letter,
        attempted_merchant_resolution=request.cardholder.attempted_merchant_resolution,
        financial_loss_confirmed=request.cardholder.financial_loss_confirmed,
    )

    evidence = [
        EvidenceItem(
            evidence_type=e.evidence_type,
            description=e.description,
            document_reference=e.document_reference,
            is_compelling=e.is_compelling,
        )
        for e in request.evidence
    ]

    task = DisputeTask(
        dispute_category=request.dispute_category,
        dispute_condition=request.dispute_condition,
        member_role=request.member_role,
        region=request.region,
        priority=request.priority,
        transaction=transaction,
        cardholder=cardholder,
        evidence=evidence,
        issuer_certification=request.issuer_certification,
        has_cardholder_letter=request.has_cardholder_letter,
        dispute_amount=request.dispute_amount,
        dispute_reason=request.dispute_reason,
        dispute_filing_date=request.dispute_filing_date or date.today(),
    )

    task_id = await brain.submit_dispute(task)

    return SubmitDisputeResponse(
        task_id=task_id,
        status=DisputeTaskStatus.PENDING,
        message="Dispute submitted for processing",
    )


@router.post("/disputes/process", response_model=DecisionResponse)
async def process_dispute_sync(request: SubmitDisputeRequest) -> DecisionResponse:
    """Submit and immediately process a dispute synchronously.

    Returns the decision directly instead of queuing for async processing.
    Useful for testing and real-time processing needs.
    """
    brain = get_brain()

    # Build the task (same as submit_dispute)
    transaction = Transaction(
        transaction_id=request.transaction.transaction_id,
        transaction_date=request.transaction.transaction_date,
        processing_date=request.transaction.processing_date,
        amount=request.transaction.amount,
        currency=request.transaction.currency,
        merchant_name=request.transaction.merchant_name,
        merchant_category_code=request.transaction.merchant_category_code,
        merchant_country=request.transaction.merchant_country,
        acquirer_bin=request.transaction.acquirer_bin,
        issuer_bin=request.transaction.issuer_bin,
        card_number_masked=request.transaction.card_number_masked,
        environment=request.transaction.environment,
        is_chip_transaction=request.transaction.is_chip_transaction,
        is_chip_reading_device=request.transaction.is_chip_reading_device,
        is_contactless=request.transaction.is_contactless,
        is_recurring=request.transaction.is_recurring,
        is_ecommerce=request.transaction.is_ecommerce,
        authorization_code=request.transaction.authorization_code,
        authorization_response_code=request.transaction.authorization_response_code,
        was_authorized=request.transaction.was_authorized,
        pos_entry_mode=request.transaction.pos_entry_mode,
        has_full_chip_data=request.transaction.has_full_chip_data,
        is_visa_secure=request.transaction.is_visa_secure,
        region=request.transaction.region,
    )

    cardholder = CardholderInfo(
        cardholder_id=request.cardholder.cardholder_id,
        account_status=request.cardholder.account_status,
        card_type=request.cardholder.card_type,
        is_chip_card=request.cardholder.is_chip_card,
        has_signed_letter=request.cardholder.has_signed_letter,
        attempted_merchant_resolution=request.cardholder.attempted_merchant_resolution,
        financial_loss_confirmed=request.cardholder.financial_loss_confirmed,
    )

    evidence = [
        EvidenceItem(
            evidence_type=e.evidence_type,
            description=e.description,
            document_reference=e.document_reference,
            is_compelling=e.is_compelling,
        )
        for e in request.evidence
    ]

    task = DisputeTask(
        dispute_category=request.dispute_category,
        dispute_condition=request.dispute_condition,
        member_role=request.member_role,
        region=request.region,
        priority=request.priority,
        transaction=transaction,
        cardholder=cardholder,
        evidence=evidence,
        issuer_certification=request.issuer_certification,
        has_cardholder_letter=request.has_cardholder_letter,
        dispute_amount=request.dispute_amount,
        dispute_reason=request.dispute_reason,
        dispute_filing_date=request.dispute_filing_date or date.today(),
    )

    decision = await brain.process_single(task)

    return _decision_to_response(decision)


@router.get("/disputes/{task_id}", response_model=DisputeStatusResponse)
async def get_dispute_status(task_id: UUID) -> DisputeStatusResponse:
    """Get the status and decision of a dispute task."""
    brain = get_brain()

    status = await brain.get_task_status(task_id)
    decision = brain.get_decision(task_id)

    if status is None and decision is None:
        raise HTTPException(status_code=404, detail=f"Dispute task {task_id} not found")

    return DisputeStatusResponse(
        task_id=task_id,
        status=status,
        decision=_decision_to_response(decision) if decision else None,
    )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_stats() -> QueueStatsResponse:
    """Get brain and queue statistics."""
    brain = get_brain()
    stats = brain.get_stats()

    queue_stats = stats.get("queue", {})
    decision_stats = stats.get("decisions", {})
    agents = stats.get("agents", [])

    return QueueStatsResponse(
        queue=queue_stats if isinstance(queue_stats, dict) else {},
        decisions=decision_stats if isinstance(decision_stats, dict) else {},
        is_running=bool(stats.get("is_running", False)),
        agents=agents if isinstance(agents, list) else [],
    )


def _decision_to_response(decision: DisputeDecision) -> DecisionResponse:
    """Convert a DisputeDecision to a DecisionResponse."""
    return DecisionResponse(
        decision_id=decision.decision_id,
        task_id=decision.task_id,
        decided_at=decision.decided_at,
        outcome=decision.outcome,
        confidence_score=decision.confidence_score,
        dispute_amount_approved=decision.dispute_amount_approved,
        reasoning=decision.reasoning,
        applicable_rules=[
            RuleEvalResponse(
                rule_id=r.rule_id,
                rule_section=r.rule_section,
                rule_description=r.rule_description,
                is_satisfied=r.is_satisfied,
                details=r.details,
            )
            for r in decision.applicable_rules
        ],
        time_limit_check=(
            TimeLimitResponse(
                is_within_time_limit=decision.time_limit_check.is_within_time_limit,
                time_limit_days=decision.time_limit_check.time_limit_days,
                start_date=decision.time_limit_check.start_date,
                deadline_date=decision.time_limit_check.deadline_date,
                days_remaining=decision.time_limit_check.days_remaining,
                rule_reference=decision.time_limit_check.rule_reference,
            )
            if decision.time_limit_check
            else None
        ),
        response_code=decision.response_code,
        response_message=decision.response_message,
        required_actions=decision.required_actions,
        escalation_reason=decision.escalation_reason,
        human_review_notes=decision.human_review_notes,
    )
