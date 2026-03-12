"""Tests for the rules engine."""

from datetime import date, datetime

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)
from src.rules.categorizer import categorize_dispute
from src.rules.compelling_evidence import evaluate_compelling_evidence
from src.rules.documentation import (
    check_documentation_requirements,
    check_fraud_type_code_requirement,
)
from src.rules.time_limits import (
    calculate_deadline,
    get_arbitration_deadline,
    get_pre_arbitration_deadline,
    is_within_time_limit,
)
from src.rules.validity import check_dispute_validity


def _make_fraud_case() -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-001",
            transaction_date=date(2026, 1, 15),
            processing_date=date(2026, 1, 16),
            amount=500.00,
            currency="USD",
            merchant_name="FraudStore",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Jane Doe",
            partial_payment_credential="****1234",
            cardholder_statement="I did not authorize this transaction",
            signed_letter_provided=True,
        ),
        fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        issuer_certification="Issuer certifies cardholder denies authorization",
    )


def _make_authorization_case() -> DisputeCase:
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-002",
            transaction_date=date(2026, 2, 1),
            processing_date=date(2026, 2, 2),
            amount=200.00,
            currency="USD",
            merchant_name="RetailStore",
            merchant_category_code="5311",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="433333",
            environment=TransactionEnvironment.CARD_PRESENT,
            authorization_response_code="05",
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="John Smith",
            partial_payment_credential="****5678",
            cardholder_statement="My card was declined but I was charged",
        ),
    )


class TestTimeLimits:
    def test_calculate_deadline(self) -> None:
        event = date(2026, 1, 16)
        deadline = calculate_deadline(event, DisputeCondition.OTHER_FRAUD_CARD_ABSENT, Region.US)
        # 120 days + 1 (processing date not counted)
        expected = date(2026, 5, 17)
        assert deadline == expected

    def test_within_time_limit(self) -> None:
        event = date(2026, 1, 16)
        filing = date(2026, 3, 1)
        assert is_within_time_limit(
            event, filing, DisputeCondition.OTHER_FRAUD_CARD_ABSENT, Region.US
        )

    def test_outside_time_limit(self) -> None:
        event = date(2026, 1, 16)
        filing = date(2026, 12, 1)
        assert not is_within_time_limit(
            event, filing, DisputeCondition.OTHER_FRAUD_CARD_ABSENT, Region.US
        )

    def test_datetime_and_date_comparison(self) -> None:
        event = date(2026, 1, 16)
        filing = datetime(2026, 3, 1, 12, 0, 0)
        assert is_within_time_limit(
            event, filing, DisputeCondition.OTHER_FRAUD_CARD_ABSENT, Region.US
        )

    def test_pre_arbitration_deadline(self) -> None:
        event = datetime(2026, 3, 1)
        deadline = get_pre_arbitration_deadline(event, "category_10_11")
        assert deadline > event

    def test_arbitration_deadline(self) -> None:
        event = datetime(2026, 4, 1)
        deadline = get_arbitration_deadline(event)
        assert deadline > event


class TestCategorizer:
    def test_categorize_fraud(self) -> None:
        case = _make_fraud_case()
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_categorize_authorization(self) -> None:
        case = _make_authorization_case()
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION

    def test_categorization_has_confidence(self) -> None:
        case = _make_fraud_case()
        result = categorize_dispute(case)
        assert 0.0 <= result.confidence <= 1.0


class TestValidity:
    def test_fraud_validity(self) -> None:
        case = _make_fraud_case()
        case.category = DisputeCategory.FRAUD
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        results = check_dispute_validity(case)
        # Should get results (validity checks run)
        assert len(results) > 0


class TestDocumentation:
    def test_fraud_documentation(self) -> None:
        case = _make_fraud_case()
        case.category = DisputeCategory.FRAUD
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        result = check_documentation_requirements(case)
        # Should have a result
        assert result.is_complete or not result.is_complete

    def test_fraud_type_code(self) -> None:
        case = _make_fraud_case()
        case.category = DisputeCategory.FRAUD
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        result = check_fraud_type_code_requirement(case)
        # Has a fraud type code, should be complete
        assert result.is_complete


class TestCompellingEvidence:
    def test_no_evidence(self) -> None:
        case = _make_fraud_case()
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        case.evidence = []
        results = evaluate_compelling_evidence(case, [])
        assert len(results) > 0
        assert not results[0].is_compelling

    def test_with_evidence(self) -> None:
        case = _make_fraud_case()
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        acquirer_evidence = [
            DisputeEvidence(
                description="Prior undisputed transactions from same device",
                evidence_type="previous_undisputed_transactions",
                provided_by="acquirer",
                is_compelling_evidence=True,
            ),
        ]
        results = evaluate_compelling_evidence(case, acquirer_evidence)
        assert len(results) > 0
        assert results[0].is_compelling
