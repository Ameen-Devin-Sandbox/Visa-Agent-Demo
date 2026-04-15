"""API routes for the Visa Disputes Processing system."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    DisputeDetailResponse,
    DisputeSubmitRequest,
    DisputeSummaryResponse,
    EscalationRequest,
    EvidenceRequest,
    HealthResponse,
    HumanReviewRequest,
    QueueStatsResponse,
)
from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.orchestrator.brain import DisputeBrain

logger = logging.getLogger(__name__)

router = APIRouter()

# Global brain instance - set during app startup
_brain: DisputeBrain | None = None


def set_brain(brain: DisputeBrain) -> None:
    """Set the global brain instance for the API routes."""
    global _brain
    _brain = brain


def get_brain() -> DisputeBrain:
    """Get the global brain instance."""
    if _brain is None:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    return _brain


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    brain = get_brain()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        agents_loaded=len(brain._agents),
        queue_depth=brain._queue.total_pending,
    )


@router.post("/disputes", response_model=DisputeSummaryResponse)
async def submit_dispute(request: DisputeSubmitRequest) -> DisputeSummaryResponse:
    """Submit a new dispute for processing.

    The dispute will be categorized, validated, and processed autonomously
    according to Visa Core Rules Section 11.
    """
    brain = get_brain()

    # Build the dispute case from the request
    transaction = TransactionDetails(
        transaction_id=request.transaction.transaction_id,
        acquirer_reference_number=request.transaction.acquirer_reference_number,
        transaction_date=request.transaction.transaction_date,
        processing_date=request.transaction.processing_date,
        amount=request.transaction.amount,
        currency=request.transaction.currency,
        merchant_name=request.transaction.merchant_name,
        merchant_category_code=request.transaction.merchant_category_code,
        merchant_country=request.transaction.merchant_country,
        acquirer_bin=request.transaction.acquirer_bin,
        issuer_bin=request.transaction.issuer_bin,
        environment=request.transaction.environment,
        is_chip_card=request.transaction.is_chip_card,
        is_chip_initiated=request.transaction.is_chip_initiated,
        is_contactless=request.transaction.is_contactless,
        is_token_transaction=request.transaction.is_token_transaction,
        is_recurring=request.transaction.is_recurring,
        pos_entry_mode=request.transaction.pos_entry_mode,
        terminal_entry_capability=request.transaction.terminal_entry_capability,
        cvv_present=request.transaction.cvv_present,
        cvv_verified=request.transaction.cvv_verified,
        avs_result_code=request.transaction.avs_result_code,
        three_d_secure_authenticated=request.transaction.three_d_secure_authenticated,
        authorization_code=request.transaction.authorization_code,
        authorization_response_code=request.transaction.authorization_response_code,
        full_chip_data_transmitted=request.transaction.full_chip_data_transmitted,
        is_fallback_transaction=request.transaction.is_fallback_transaction,
        is_delayed_charge=request.transaction.is_delayed_charge,
        is_mobile_push_payment=request.transaction.is_mobile_push_payment,
        is_emergency_cash_disbursement=request.transaction.is_emergency_cash_disbursement,
        is_veps_transaction=request.transaction.is_veps_transaction,
        region=request.transaction.region,
    )

    cardholder = CardholderInfo(
        cardholder_name=request.cardholder.cardholder_name,
        partial_payment_credential=request.cardholder.partial_payment_credential,
        contact_email=request.cardholder.contact_email,
        contact_phone=request.cardholder.contact_phone,
        cardholder_statement=request.cardholder.cardholder_statement,
        signed_letter_provided=request.cardholder.signed_letter_provided,
    )

    evidence_list = [
        DisputeEvidence(
            description=e.description,
            evidence_type=e.evidence_type,
            provided_by=e.provided_by,
            is_compelling_evidence=e.is_compelling_evidence,
            document_references=e.document_references,
        )
        for e in request.evidence
    ]

    case = DisputeCase(
        transaction=transaction,
        cardholder=cardholder,
        fraud_type_code=request.fraud_type_code,
        evidence=evidence_list,
        issuer_certification=request.issuer_certification,
        dispute_amount=request.dispute_amount,
        dispute_currency=request.dispute_currency,
    )

    # Process synchronously for immediate response
    processed = await brain.process_single(case)

    summary = brain.get_case_summary(processed.case_id)
    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to process dispute")

    return DisputeSummaryResponse(**summary)


@router.get("/disputes", response_model=list[DisputeSummaryResponse])
async def list_disputes() -> list[DisputeSummaryResponse]:
    """List all dispute cases."""
    brain = get_brain()
    cases = brain.get_all_cases()
    summaries = []
    for case in cases:
        summary = brain.get_case_summary(case.case_id)
        if summary:
            summaries.append(DisputeSummaryResponse(**summary))
    return summaries


@router.get("/disputes/{case_id}", response_model=DisputeDetailResponse)
async def get_dispute(case_id: str) -> DisputeDetailResponse:
    """Get detailed information about a dispute case."""
    brain = get_brain()
    case = brain.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    return DisputeDetailResponse(
        case_id=case.case_id,
        stage=case.stage.value,
        category=case.category.value if case.category else None,
        condition=case.condition.value if case.condition else None,
        transaction_id=case.transaction.transaction_id,
        transaction_amount=case.transaction.amount,
        transaction_currency=case.transaction.currency,
        merchant_name=case.transaction.merchant_name,
        transaction_environment=case.transaction.environment.value,
        resolution=case.decision.resolution.value if case.decision else None,
        rationale=case.decision.rationale if case.decision else None,
        confidence=case.decision.confidence_score if case.decision else None,
        requires_human_review=case.decision.requires_human_review if case.decision else False,
        decided_by=case.decision.decided_by if case.decision else None,
        rule_evaluations=[
            {
                "rule_id": r.rule_id,
                "rule_section": r.rule_section,
                "description": r.rule_description,
                "satisfied": r.is_satisfied,
                "details": r.details,
            }
            for r in case.rule_evaluations
        ],
        evidence=[
            {
                "evidence_id": e.evidence_id,
                "description": e.description,
                "type": e.evidence_type,
                "provided_by": e.provided_by,
                "is_compelling": e.is_compelling_evidence,
            }
            for e in case.evidence
        ],
        processing_notes=case.processing_notes,
        stage_history=case.stage_history,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
    )


@router.post("/disputes/{case_id}/review", response_model=DisputeSummaryResponse)
async def human_review(case_id: str, request: HumanReviewRequest) -> DisputeSummaryResponse:
    """Submit a human review decision for a case in HUMAN_REVIEW stage."""
    brain = get_brain()
    result = await brain.approve_human_review(
        case_id=case_id,
        approved=request.approved,
        reviewer_notes=request.reviewer_notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    summary = brain.get_case_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to get case summary")
    return DisputeSummaryResponse(**summary)


@router.post("/disputes/{case_id}/pre-arbitration", response_model=DisputeSummaryResponse)
async def escalate_pre_arbitration(
    case_id: str,
    request: EscalationRequest,
) -> DisputeSummaryResponse:
    """Escalate a dispute to pre-arbitration.

    Used when the acquirer contests the initial dispute decision.
    """
    brain = get_brain()
    case = brain.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Add acquirer evidence
    for e in request.acquirer_evidence:
        case.add_evidence(
            DisputeEvidence(
                description=e.description,
                evidence_type=e.evidence_type,
                provided_by="acquirer",
                is_compelling_evidence=e.is_compelling_evidence,
                document_references=e.document_references,
            )
        )

    result = await brain.escalate_to_pre_arbitration(case_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Failed to escalate to pre-arbitration")

    summary = brain.get_case_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to get case summary")
    return DisputeSummaryResponse(**summary)


@router.post("/disputes/{case_id}/arbitration", response_model=DisputeSummaryResponse)
async def escalate_arbitration(case_id: str) -> DisputeSummaryResponse:
    """Escalate a dispute to arbitration after pre-arbitration cycle."""
    brain = get_brain()
    result = await brain.escalate_to_arbitration(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    summary = brain.get_case_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to get case summary")
    return DisputeSummaryResponse(**summary)


@router.post("/disputes/{case_id}/evidence", response_model=DisputeSummaryResponse)
async def add_evidence(case_id: str, request: EvidenceRequest) -> DisputeSummaryResponse:
    """Add evidence to an existing dispute case."""
    brain = get_brain()
    case = brain.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case.add_evidence(
        DisputeEvidence(
            description=request.description,
            evidence_type=request.evidence_type,
            provided_by=request.provided_by,
            is_compelling_evidence=request.is_compelling_evidence,
            document_references=request.document_references,
        )
    )

    summary = brain.get_case_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to get case summary")
    return DisputeSummaryResponse(**summary)


@router.get("/queue/stats", response_model=QueueStatsResponse)
async def queue_stats() -> QueueStatsResponse:
    """Get task queue statistics."""
    brain = get_brain()
    return QueueStatsResponse(
        queue_depth=brain._queue.get_queue_depth(),
        stats=brain._queue.get_stats(),
    )
