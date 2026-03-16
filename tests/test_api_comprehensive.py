"""Comprehensive tests for the FastAPI API endpoints.

Tests all REST endpoints using the ASGI test client.
"""


import pytest
from fastapi.testclient import TestClient

from src.api.routes import set_brain
from src.app import app
from src.orchestrator.brain import DisputeBrain
from src.queue.task_queue import DisputeTaskQueue


@pytest.fixture
def brain() -> DisputeBrain:
    queue = DisputeTaskQueue()
    brain = DisputeBrain(queue)
    set_brain(brain)
    return brain


@pytest.fixture
def client(brain: DisputeBrain) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _fraud_request() -> dict:
    return {
        "transaction": {
            "transaction_id": "TXN-API-001",
            "transaction_date": "2026-02-15",
            "processing_date": "2026-02-16",
            "amount": 500.0,
            "currency": "USD",
            "merchant_name": "TestMerchant",
            "environment": "ecommerce",
        },
        "cardholder": {
            "cardholder_name": "Test User",
            "partial_payment_credential": "****1234",
            "cardholder_statement": "This was an unauthorized transaction",
        },
        "fraud_type_code": "7",  # FraudTypeCode.ACCOUNT_TAKEOVER
        "issuer_certification": "Cardholder denies authorization",
    }


def _consumer_request() -> dict:
    return {
        "transaction": {
            "transaction_id": "TXN-API-002",
            "transaction_date": "2026-02-15",
            "processing_date": "2026-02-16",
            "amount": 200.0,
            "currency": "USD",
            "merchant_name": "OnlineStore",
            "environment": "ecommerce",
            "authorization_code": "ABC123",
            "authorization_response_code": "00",
        },
        "cardholder": {
            "cardholder_name": "Jane Doe",
            "partial_payment_credential": "****5678",
            "cardholder_statement": "I never received my order",
        },
        "evidence": [
            {
                "description": "Order receipt showing expected delivery date",
                "evidence_type": "receipt",
                "provided_by": "issuer",
            }
        ],
    }


def _auth_request() -> dict:
    return {
        "transaction": {
            "transaction_id": "TXN-API-003",
            "transaction_date": "2026-02-15",
            "processing_date": "2026-02-16",
            "amount": 300.0,
            "currency": "USD",
            "merchant_name": "RetailStore",
            "environment": "card_present",
            "authorization_response_code": "14",  # Non-zero start = declined
        },
        "cardholder": {
            "cardholder_name": "Bob Smith",
            "partial_payment_credential": "****9012",
            "cardholder_statement": "My card was declined but I was charged",
        },
        "evidence": [
            {
                "description": "Decline response record",
                "evidence_type": "auth_record",
                "provided_by": "issuer",
            }
        ],
    }


# ============================================================================
# Health and root endpoints
# ============================================================================


class TestHealthEndpoints:
    def test_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Visa Disputes Processing Brain"
        assert data["version"] == "0.1.0"

    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agents_loaded"] == 5
        assert data["queue_depth"] == 0


# ============================================================================
# Submit disputes
# ============================================================================


class TestSubmitDispute:
    def test_submit_fraud_dispute(self, client: TestClient) -> None:
        response = client.post("/api/v1/disputes", json=_fraud_request())
        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] is not None
        assert data["category"] is not None
        assert data["resolution"] is not None
        assert data["assigned_agent"] is not None

    def test_submit_consumer_dispute(self, client: TestClient) -> None:
        response = client.post("/api/v1/disputes", json=_consumer_request())
        assert response.status_code == 200
        data = response.json()
        # DisputeCategory.CONSUMER_DISPUTES.value == "13"
        assert data["category"] == "13"

    def test_submit_auth_dispute(self, client: TestClient) -> None:
        response = client.post("/api/v1/disputes", json=_auth_request())
        assert response.status_code == 200
        data = response.json()
        # DisputeCategory.AUTHORIZATION.value == "11"
        assert data["category"] == "11"

    def test_submit_dispute_includes_confidence(self, client: TestClient) -> None:
        response = client.post("/api/v1/disputes", json=_fraud_request())
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] is not None
        assert 0.0 <= data["confidence"] <= 1.0

    def test_submit_with_evidence(self, client: TestClient) -> None:
        req = _fraud_request()
        req["evidence"] = [
            {
                "description": "Fraud report filed with police",
                "evidence_type": "police_report",
                "provided_by": "issuer",
            }
        ]
        response = client.post("/api/v1/disputes", json=req)
        assert response.status_code == 200
        data = response.json()
        assert data["evidence_count"] >= 1


# ============================================================================
# List and get disputes
# ============================================================================


class TestListAndGetDisputes:
    def test_list_disputes_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/disputes")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_disputes_after_submit(self, client: TestClient) -> None:
        resp1 = client.post("/api/v1/disputes", json=_fraud_request())
        resp2 = client.post("/api/v1/disputes", json=_consumer_request())
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        response = client.get("/api/v1/disputes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_dispute_detail(self, client: TestClient) -> None:
        submit_response = client.post("/api/v1/disputes", json=_fraud_request())
        assert submit_response.status_code == 200
        case_id = submit_response.json()["case_id"]

        response = client.get(f"/api/v1/disputes/{case_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["case_id"] == case_id
        assert detail["transaction_id"] == "TXN-API-001"
        assert detail["transaction_amount"] == 500.0
        assert detail["merchant_name"] == "TestMerchant"
        assert len(detail["rule_evaluations"]) > 0
        assert len(detail["stage_history"]) > 0
        assert len(detail["processing_notes"]) > 0

    def test_get_dispute_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/disputes/nonexistent")
        assert response.status_code == 404


# ============================================================================
# Human review
# ============================================================================


class TestHumanReview:
    def test_approve_review(self, client: TestClient) -> None:
        # Submit a case that may need human review
        req = _fraud_request()
        req.pop("issuer_certification")
        submit_response = client.post("/api/v1/disputes", json=req)
        assert submit_response.status_code == 200
        data = submit_response.json()
        case_id = data["case_id"]

        if data.get("requires_human_review"):
            response = client.post(
                f"/api/v1/disputes/{case_id}/review",
                json={"approved": True, "reviewer_notes": "Approved"},
            )
            assert response.status_code == 200
            assert response.json()["stage"] == "resolved"

    def test_review_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/disputes/nonexistent/review",
            json={"approved": True},
        )
        assert response.status_code == 404


# ============================================================================
# Evidence submission
# ============================================================================


class TestEvidenceSubmission:
    def test_add_evidence(self, client: TestClient) -> None:
        submit_response = client.post("/api/v1/disputes", json=_fraud_request())
        assert submit_response.status_code == 200
        case_id = submit_response.json()["case_id"]

        response = client.post(
            f"/api/v1/disputes/{case_id}/evidence",
            json={
                "description": "Additional fraud documentation",
                "evidence_type": "fraud_report",
                "provided_by": "issuer",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evidence_count"] >= 1

    def test_add_evidence_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/disputes/nonexistent/evidence",
            json={
                "description": "Test",
                "evidence_type": "test",
                "provided_by": "issuer",
            },
        )
        assert response.status_code == 404


# ============================================================================
# Escalation endpoints
# ============================================================================


class TestEscalation:
    def test_escalate_pre_arbitration(self, client: TestClient) -> None:
        submit_response = client.post("/api/v1/disputes", json=_fraud_request())
        assert submit_response.status_code == 200
        case_id = submit_response.json()["case_id"]

        response = client.post(
            f"/api/v1/disputes/{case_id}/pre-arbitration",
            json={
                "acquirer_evidence": [
                    {
                        "description": "Delivery to verified address",
                        "evidence_type": "delivery_confirmation",
                        "is_compelling_evidence": True,
                    }
                ]
            },
        )
        assert response.status_code == 200

    def test_escalate_pre_arbitration_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/disputes/nonexistent/pre-arbitration",
            json={"acquirer_evidence": []},
        )
        assert response.status_code == 404

    def test_escalate_arbitration(self, client: TestClient) -> None:
        submit_response = client.post("/api/v1/disputes", json=_fraud_request())
        assert submit_response.status_code == 200
        case_id = submit_response.json()["case_id"]

        response = client.post(f"/api/v1/disputes/{case_id}/arbitration")
        assert response.status_code == 200
        data = response.json()
        assert data["resolution"] == "escalated_arbitration"

    def test_escalate_arbitration_not_found(self, client: TestClient) -> None:
        response = client.post("/api/v1/disputes/nonexistent/arbitration")
        assert response.status_code == 404


# ============================================================================
# Queue stats
# ============================================================================


class TestQueueStats:
    def test_queue_stats(self, client: TestClient) -> None:
        response = client.get("/api/v1/queue/stats")
        assert response.status_code == 200
        data = response.json()
        assert "queue_depth" in data
        assert "stats" in data
