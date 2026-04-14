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

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Build a TransactionDetails from request.transaction (map all fields).
      3. Build a CardholderInfo from request.cardholder (map all fields).
      4. Build a list of DisputeEvidence from request.evidence.
      5. Create a DisputeCase with the above objects plus fraud_type_code,
         issuer_certification, dispute_amount, and dispute_currency from the request.
      6. Call `await brain.process_single(case)` to process the dispute.
      7. Call `brain.get_case_summary(processed.case_id)` to get the summary.
      8. Return a DisputeSummaryResponse(**summary).
      9. Raise HTTPException(500) if the summary is None.
    """
    raise NotImplementedError("Module 5: Implement submit_dispute endpoint")


@router.get("/disputes", response_model=list[DisputeSummaryResponse])
async def list_disputes() -> list[DisputeSummaryResponse]:
    """List all dispute cases.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call brain.get_all_cases() to retrieve every case.
      3. For each case, call brain.get_case_summary(case.case_id).
      4. Collect non-None summaries into a list of DisputeSummaryResponse.
      5. Return the list.
    """
    raise NotImplementedError("Module 5: Implement list_disputes endpoint")


@router.get("/disputes/{case_id}", response_model=DisputeDetailResponse)
async def get_dispute(case_id: str) -> DisputeDetailResponse:
    """Get detailed information about a dispute case.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call brain.get_case(case_id). Raise HTTPException(404) if None.
      3. Build and return a DisputeDetailResponse with:
         - case_id, stage (.value), category (.value or None), condition (.value or None)
         - Transaction fields: transaction_id, amount, currency, merchant_name, environment (.value)
         - Decision fields (from case.decision, or defaults if None): resolution, rationale,
           confidence, requires_human_review, decided_by
         - rule_evaluations: list of dicts with rule_id, rule_section, description,
           satisfied, details
         - evidence: list of dicts with evidence_id, description, type, provided_by, is_compelling
         - processing_notes, stage_history
         - created_at and updated_at as .isoformat() strings
    """
    raise NotImplementedError("Module 5: Implement get_dispute endpoint")


@router.post("/disputes/{case_id}/review", response_model=DisputeSummaryResponse)
async def human_review(case_id: str, request: HumanReviewRequest) -> DisputeSummaryResponse:
    """Submit a human review decision for a case in HUMAN_REVIEW stage.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call `await brain.approve_human_review(case_id, approved, reviewer_notes)`.
      3. Raise HTTPException(404) if the result is None.
      4. Call brain.get_case_summary(case_id) and return DisputeSummaryResponse(**summary).
      5. Raise HTTPException(500) if the summary is None.
    """
    raise NotImplementedError("Module 5: Implement human_review endpoint")


@router.post("/disputes/{case_id}/pre-arbitration", response_model=DisputeSummaryResponse)
async def escalate_pre_arbitration(
    case_id: str,
    request: EscalationRequest,
) -> DisputeSummaryResponse:
    """Escalate a dispute to pre-arbitration.

    Used when the acquirer contests the initial dispute decision.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call brain.get_case(case_id). Raise HTTPException(404) if None.
      3. For each item in request.acquirer_evidence, create a DisputeEvidence
         (with provided_by="acquirer") and call case.add_evidence(...).
      4. Call `await brain.escalate_to_pre_arbitration(case_id)`.
      5. Raise HTTPException(400) if the result is None.
      6. Call brain.get_case_summary(case_id) and return DisputeSummaryResponse(**summary).
      7. Raise HTTPException(500) if the summary is None.
    """
    raise NotImplementedError("Module 5: Implement escalate_pre_arbitration endpoint")


@router.post("/disputes/{case_id}/arbitration", response_model=DisputeSummaryResponse)
async def escalate_arbitration(case_id: str) -> DisputeSummaryResponse:
    """Escalate a dispute to arbitration after pre-arbitration cycle.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call `await brain.escalate_to_arbitration(case_id)`.
      3. Raise HTTPException(404) if the result is None.
      4. Call brain.get_case_summary(case_id) and return DisputeSummaryResponse(**summary).
      5. Raise HTTPException(500) if the summary is None.
    """
    raise NotImplementedError("Module 5: Implement escalate_arbitration endpoint")


@router.post("/disputes/{case_id}/evidence", response_model=DisputeSummaryResponse)
async def add_evidence(case_id: str, request: EvidenceRequest) -> DisputeSummaryResponse:
    """Add evidence to an existing dispute case.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Call brain.get_case(case_id). Raise HTTPException(404) if None.
      3. Create a DisputeEvidence from the request fields (description, evidence_type,
         provided_by, is_compelling_evidence, document_references).
      4. Call case.add_evidence(...) with the new evidence.
      5. Call brain.get_case_summary(case_id) and return DisputeSummaryResponse(**summary).
      6. Raise HTTPException(500) if the summary is None.
    """
    raise NotImplementedError("Module 5: Implement add_evidence endpoint")


@router.get("/queue/stats", response_model=QueueStatsResponse)
async def queue_stats() -> QueueStatsResponse:
    """Get task queue statistics.

    TODO: Implement this endpoint.
    Steps:
      1. Get the brain via get_brain().
      2. Return a QueueStatsResponse with:
         - queue_depth from brain._queue.get_queue_depth()
         - stats from brain._queue.get_stats()
    """
    raise NotImplementedError("Module 5: Implement queue_stats endpoint")
