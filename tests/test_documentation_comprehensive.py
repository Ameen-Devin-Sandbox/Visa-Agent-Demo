"""Comprehensive tests for documentation and certification requirement validators."""

from datetime import date

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    DisputeCondition,
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)
from src.rules.documentation import (
    DOCUMENTATION_REQUIREMENTS,
    check_documentation_requirements,
    check_fraud_type_code_requirement,
)


def _make_case(
    condition: DisputeCondition | None = None,
    fraud_type_code: FraudTypeCode | None = None,
    issuer_certification: str | None = None,
    signed_letter: bool = False,
    evidence: list[DisputeEvidence] | None = None,
) -> DisputeCase:
    case = DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-DOC-001",
            transaction_date=date(2026, 2, 15),
            processing_date=date(2026, 2, 16),
            amount=100.0,
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
            signed_letter_provided=signed_letter,
        ),
        condition=condition,
        fraud_type_code=fraud_type_code,
        issuer_certification=issuer_certification,
        evidence=evidence or [],
    )
    return case


# ============================================================================
# Documentation requirements registry
# ============================================================================


class TestDocumentationRequirementsRegistry:
    """Test that the requirements registry is complete."""

    def test_all_fraud_conditions_have_requirements(self) -> None:
        for cond in [
            DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
        ]:
            assert cond in DOCUMENTATION_REQUIREMENTS

    def test_all_auth_conditions_have_requirements(self) -> None:
        for cond in [
            DisputeCondition.CARD_RECOVERY_BULLETIN,
            DisputeCondition.DECLINED_AUTHORIZATION,
            DisputeCondition.NO_AUTHORIZATION,
        ]:
            assert cond in DOCUMENTATION_REQUIREMENTS

    def test_all_processing_error_conditions_have_requirements(self) -> None:
        for cond in [
            DisputeCondition.INCORRECT_TRANSACTION_CODE,
            DisputeCondition.INCORRECT_CURRENCY,
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER,
            DisputeCondition.INCORRECT_AMOUNT,
            DisputeCondition.DUPLICATE_PROCESSING,
            DisputeCondition.INVALID_DATA,
        ]:
            assert cond in DOCUMENTATION_REQUIREMENTS

    def test_all_consumer_conditions_have_requirements(self) -> None:
        for cond in [
            DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            DisputeCondition.CANCELLED_RECURRING,
            DisputeCondition.NOT_AS_DESCRIBED,
            DisputeCondition.COUNTERFEIT_MERCHANDISE,
            DisputeCondition.MISREPRESENTATION,
            DisputeCondition.CREDIT_NOT_PROCESSED,
            DisputeCondition.CANCELLED_MERCHANDISE,
            DisputeCondition.OCT_NOT_ACCEPTED,
            DisputeCondition.NON_RECEIPT_CASH_ATM,
        ]:
            assert cond in DOCUMENTATION_REQUIREMENTS

    def test_requirements_have_mandatory_flag(self) -> None:
        for _cond, reqs in DOCUMENTATION_REQUIREMENTS.items():
            for req in reqs:
                assert isinstance(req.is_mandatory, bool)


# ============================================================================
# check_documentation_requirements
# ============================================================================


class TestCheckDocumentationRequirements:
    """Test the main documentation requirement checker."""

    def test_no_condition_incomplete(self) -> None:
        case = _make_case(condition=None)
        result = check_documentation_requirements(case)
        assert not result.is_complete
        assert "condition_not_assigned" in result.missing_requirements

    def test_fraud_with_certification_and_code(self) -> None:
        """Fraud dispute with all docs → complete."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
        )
        result = check_documentation_requirements(case)
        assert result.is_complete

    def test_fraud_with_signed_letter(self) -> None:
        """Signed letter fulfills certification requirement."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            signed_letter=True,
        )
        result = check_documentation_requirements(case)
        assert result.is_complete

    def test_fraud_missing_certification(self) -> None:
        """Fraud without certification → incomplete."""
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = check_documentation_requirements(case)
        assert not result.is_complete
        assert len(result.missing_requirements) > 0

    def test_emv_counterfeit_missing_code(self) -> None:
        """10.1 without fraud report → incomplete."""
        case = _make_case(
            condition=DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            issuer_certification="Cardholder denies participation",
        )
        result = check_documentation_requirements(case)
        assert not result.is_complete

    def test_consumer_with_evidence(self) -> None:
        """Consumer dispute with evidence → complete."""
        evidence = [
            DisputeEvidence(
                description="Item never received",
                evidence_type="statement",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED,
            evidence=evidence,
        )
        result = check_documentation_requirements(case)
        assert result.is_complete

    def test_consumer_missing_evidence(self) -> None:
        """Consumer dispute without evidence → incomplete."""
        case = _make_case(
            condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED,
        )
        result = check_documentation_requirements(case)
        assert not result.is_complete

    def test_auth_declined_with_evidence(self) -> None:
        evidence = [
            DisputeEvidence(
                description="Decline response record",
                evidence_type="authorization_record",
                provided_by="issuer",
            ),
        ]
        case = _make_case(
            condition=DisputeCondition.DECLINED_AUTHORIZATION,
            evidence=evidence,
        )
        result = check_documentation_requirements(case)
        assert result.is_complete

    def test_met_requirements_listed(self) -> None:
        case = _make_case(
            condition=DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            issuer_certification="Cardholder denies authorization",
        )
        result = check_documentation_requirements(case)
        assert len(result.met_requirements) > 0


# ============================================================================
# check_fraud_type_code_requirement
# ============================================================================


class TestCheckFraudTypeCodeRequirement:
    """Test fraud type code requirement checks."""

    def test_no_condition(self) -> None:
        case = _make_case(condition=None)
        result = check_fraud_type_code_requirement(case)
        assert not result.is_complete

    def test_non_fraud_condition_no_requirement(self) -> None:
        """Non-fraud conditions have no fraud code requirement."""
        case = _make_case(condition=DisputeCondition.MERCHANDISE_NOT_RECEIVED)
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete

    def test_10_1_requires_counterfeit_code(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
        )
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete

    def test_10_1_wrong_code(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = check_fraud_type_code_requirement(case)
        assert not result.is_complete
        assert "fraud_type_code_mismatch" in result.missing_requirements

    def test_10_1_no_code(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_COUNTERFEIT_FRAUD,
            fraud_type_code=None,
        )
        result = check_fraud_type_code_requirement(case)
        assert not result.is_complete

    def test_10_2_accepts_lost(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.LOST,
        )
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete

    def test_10_2_accepts_stolen(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.STOLEN,
        )
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete

    def test_10_2_accepts_not_received(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.NOT_RECEIVED,
        )
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete

    def test_10_2_wrong_code(self) -> None:
        case = _make_case(
            condition=DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD,
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
        )
        result = check_fraud_type_code_requirement(case)
        assert not result.is_complete

    def test_10_3_no_specific_requirement(self) -> None:
        """10.3 doesn't require specific fraud type codes."""
        case = _make_case(condition=DisputeCondition.OTHER_FRAUD_CARD_PRESENT)
        result = check_fraud_type_code_requirement(case)
        assert result.is_complete
