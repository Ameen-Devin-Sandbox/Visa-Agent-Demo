"""Tests for data models."""

from datetime import date

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    RuleEvaluationResult,
    TimeLimit,
    TransactionDetails,
)
from src.models.enums import (
    DisputeLifecycleStage,
    Region,
    TaskPriority,
    TransactionEnvironment,
)
from src.models.task import DisputeTask


def _make_case() -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-001",
            transaction_date=date(2026, 1, 15),
            processing_date=date(2026, 1, 16),
            amount=100.00,
            currency="USD",
            merchant_name="TestMerchant",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Test User",
            partial_payment_credential="****1234",
        ),
    )


class TestTransactionDetails:
    def test_create_transaction(self) -> None:
        txn = TransactionDetails(
            transaction_id="TXN-001",
            transaction_date=date(2026, 1, 15),
            processing_date=date(2026, 1, 16),
            amount=100.00,
            currency="USD",
            merchant_name="TestMerchant",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
        )
        assert txn.transaction_id == "TXN-001"
        assert txn.amount == 100.00
        assert txn.region == Region.GLOBAL


class TestDisputeCase:
    def test_create_case(self) -> None:
        case = _make_case()
        assert case.case_id is not None
        assert case.stage == DisputeLifecycleStage.INTAKE

    def test_advance_stage(self) -> None:
        case = _make_case()
        case.advance_stage(DisputeLifecycleStage.VALIDATION, "Testing")
        assert case.stage == DisputeLifecycleStage.VALIDATION
        assert len(case.stage_history) == 1
        assert case.stage_history[0]["from_stage"] == "intake"
        assert case.stage_history[0]["to_stage"] == "validation"

    def test_add_evidence(self) -> None:
        case = _make_case()
        evidence = DisputeEvidence(
            description="Test evidence",
            evidence_type="document",
            provided_by="issuer",
        )
        case.add_evidence(evidence)
        assert len(case.evidence) == 1

    def test_add_processing_note(self) -> None:
        case = _make_case()
        case.add_processing_note("Test note")
        assert len(case.processing_notes) == 1

    def test_add_rule_evaluation(self) -> None:
        case = _make_case()
        evaluation = RuleEvaluationResult(
            rule_id="test_rule",
            rule_section="11.1",
            rule_description="Test rule",
            is_satisfied=True,
            details="Passed",
        )
        case.add_rule_evaluation(evaluation)
        assert len(case.rule_evaluations) == 1


class TestTimeLimit:
    def test_basic_time_limit(self) -> None:
        tl = TimeLimit(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 days",
        )
        assert tl.calendar_days == 120

    def test_time_limit_with_exceptions(self) -> None:
        tl = TimeLimit(
            calendar_days=120,
            from_event="transaction_processing_date",
            region_exceptions={"europe": 540},
            description="120 days with exceptions",
        )
        assert tl.region_exceptions["europe"] == 540


class TestDisputeTask:
    def test_create_task(self) -> None:
        task = DisputeTask(case_id="case-001", action="process_dispute")
        assert task.task_id is not None
        assert task.priority == TaskPriority.MEDIUM

    def test_mark_in_progress(self) -> None:
        task = DisputeTask(case_id="case-001", action="process_dispute")
        task.mark_in_progress("test_agent")
        assert task.assigned_agent == "test_agent"
        assert task.started_at is not None

    def test_mark_completed(self) -> None:
        task = DisputeTask(case_id="case-001", action="process_dispute")
        task.mark_in_progress("test_agent")
        task.mark_completed({"result": "ok"})
        assert task.completed_at is not None
        assert task.result == {"result": "ok"}

    def test_mark_failed_with_retry(self) -> None:
        task = DisputeTask(case_id="case-001", action="process_dispute")
        task.mark_in_progress("test_agent")
        task.mark_failed("test error")
        assert task.retry_count == 1
        assert task.error_message == "test error"
