"""Comprehensive tests for the dispute categorization engine.

Tests all dispute categories (10, 11, 12, 13) with various conditions,
edge cases, and confidence scoring.
"""

from datetime import date

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
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


def _base_transaction(**overrides: object) -> TransactionDetails:
    """Create a base transaction with optional overrides."""
    defaults = {
        "transaction_id": "TXN-TEST-001",
        "transaction_date": date(2026, 2, 15),
        "processing_date": date(2026, 2, 16),
        "amount": 500.00,
        "currency": "USD",
        "merchant_name": "TestMerchant",
        "merchant_category_code": "5411",
        "merchant_country": "US",
        "acquirer_bin": "411111",
        "issuer_bin": "422222",
        "environment": TransactionEnvironment.ECOMMERCE,
        "region": Region.US,
    }
    defaults.update(overrides)
    return TransactionDetails(**defaults)


def _make_case(
    statement: str | None = None,
    fraud_type_code: FraudTypeCode | None = None,
    issuer_certification: str | None = None,
    **txn_overrides: object,
) -> DisputeCase:
    """Create a dispute case with given parameters."""
    return DisputeCase(
        transaction=_base_transaction(**txn_overrides),
        cardholder=CardholderInfo(
            cardholder_name="Test User",
            partial_payment_credential="****1234",
            cardholder_statement=statement,
        ),
        fraud_type_code=fraud_type_code,
        issuer_certification=issuer_certification,
    )


# ============================================================================
# Category 10: Fraud Disputes
# ============================================================================


class TestFraudCategorization:
    """Test Category 10 fraud dispute categorization."""

    def test_fraud_by_type_code_account_takeover(self) -> None:
        """Fraud type code triggers Category 10 regardless of statement."""
        case = _make_case(
            statement="Generic statement",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_type_code_counterfeit(self) -> None:
        case = _make_case(
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
            environment=TransactionEnvironment.CARD_PRESENT,
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_type_code_lost(self) -> None:
        case = _make_case(fraud_type_code=FraudTypeCode.LOST)
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_type_code_stolen(self) -> None:
        case = _make_case(fraud_type_code=FraudTypeCode.STOLEN)
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_statement_unauthorized(self) -> None:
        """Statement containing 'unauthorized' triggers fraud."""
        case = _make_case(statement="This was an unauthorized transaction")
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_statement_did_not_authorize(self) -> None:
        case = _make_case(statement="I did not authorize this purchase")
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_statement_identity_theft(self) -> None:
        case = _make_case(statement="This is identity theft on my account")
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_by_statement_not_mine(self) -> None:
        case = _make_case(statement="This transaction is not mine")
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_condition_10_4_card_absent_ecommerce(self) -> None:
        """E-commerce fraud maps to 10.4 (Card-Absent)."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            environment=TransactionEnvironment.ECOMMERCE,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.OTHER_FRAUD_CARD_ABSENT

    def test_condition_10_4_card_absent_moto(self) -> None:
        """MOTO fraud maps to 10.4."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            environment=TransactionEnvironment.MOTO,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.OTHER_FRAUD_CARD_ABSENT

    def test_condition_10_3_card_present_fraud(self) -> None:
        """Card-present fraud without chip maps to 10.3."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            environment=TransactionEnvironment.CARD_PRESENT,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.OTHER_FRAUD_CARD_PRESENT

    def test_condition_10_1_emv_counterfeit(self) -> None:
        """EMV counterfeit fraud with chip card at non-chip terminal."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.COUNTERFEIT,
            environment=TransactionEnvironment.CARD_PRESENT,
            is_chip_card=True,
            terminal_entry_capability="2",  # Not "5" (chip-capable)
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.EMV_COUNTERFEIT_FRAUD
        assert result.confidence >= 0.90

    def test_condition_10_2_emv_non_counterfeit_lost(self) -> None:
        """Lost card chip transaction maps to 10.2."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.LOST,
            environment=TransactionEnvironment.CARD_PRESENT,
            is_chip_card=True,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD

    def test_condition_10_2_emv_non_counterfeit_stolen(self) -> None:
        """Stolen card chip transaction maps to 10.2."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.STOLEN,
            environment=TransactionEnvironment.CARD_PRESENT,
            is_chip_card=True,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD

    def test_fraud_alternatives_include_monitoring(self) -> None:
        """Fraud categorization includes VISA_FRAUD_MONITORING as alternative."""
        case = _make_case(
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            environment=TransactionEnvironment.ECOMMERCE,
        )
        result = categorize_dispute(case)
        assert DisputeCondition.VISA_FRAUD_MONITORING in result.alternative_conditions

    def test_fraud_confidence_above_threshold(self) -> None:
        """All fraud categorizations should have reasonable confidence."""
        case = _make_case(fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER)
        result = categorize_dispute(case)
        assert result.confidence >= 0.60


# ============================================================================
# Category 11: Authorization Disputes
# ============================================================================


class TestAuthorizationCategorization:
    """Test Category 11 authorization dispute categorization."""

    def test_condition_11_2_declined_auth(self) -> None:
        """Declined authorization code (non-zero start) triggers 11.2."""
        case = _make_case(
            statement="My card was declined but I was charged",
            authorization_response_code="14",  # Non-zero start = declined
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION
        assert result.condition == DisputeCondition.DECLINED_AUTHORIZATION

    def test_condition_11_2_high_confidence(self) -> None:
        """Declined auth with explicit response code has high confidence."""
        case = _make_case(
            statement="My card was declined",
            authorization_response_code="14",
        )
        result = categorize_dispute(case)
        assert result.confidence >= 0.90

    def test_condition_11_3_no_auth_code(self) -> None:
        """Missing authorization code triggers 11.3."""
        case = _make_case(
            statement="No authorization for this charge",
            authorization_code=None,
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION
        assert result.condition == DisputeCondition.NO_AUTHORIZATION

    def test_condition_11_1_card_recovery_bulletin(self) -> None:
        """Card recovery bulletin statement triggers 11.1."""
        case = _make_case(
            statement="This card was on card recovery bulletin",
            authorization_code=None,
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION
        assert result.condition == DisputeCondition.CARD_RECOVERY_BULLETIN

    def test_auth_by_statement_declined(self) -> None:
        """Statement with 'declined' triggers authorization category."""
        case = _make_case(
            statement="Transaction was declined but still went through",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION

    def test_auth_by_statement_expired_card(self) -> None:
        """Statement with 'expired card' triggers authorization category."""
        case = _make_case(
            statement="Used an expired card",
            authorization_code=None,
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION


# ============================================================================
# Category 12: Processing Error Disputes
# ============================================================================


class TestProcessingErrorCategorization:
    """Test Category 12 processing error categorization."""

    def test_condition_12_5_incorrect_amount(self) -> None:
        """Statement about incorrect amount maps to 12.5."""
        case = _make_case(
            statement="I was charged an incorrect amount",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.PROCESSING_ERRORS
        assert result.condition == DisputeCondition.INCORRECT_AMOUNT

    def test_condition_12_5_wrong_amount(self) -> None:
        case = _make_case(
            statement="The wrong amount was charged to my card",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.INCORRECT_AMOUNT

    def test_condition_12_6_duplicate(self) -> None:
        """Statement about duplicate charges maps to 12.6."""
        case = _make_case(
            statement="I was charged twice for this duplicate transaction",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.PROCESSING_ERRORS
        assert result.condition == DisputeCondition.DUPLICATE_PROCESSING

    def test_condition_12_6_paid_by_other_means(self) -> None:
        case = _make_case(
            statement="I already paid by other means for this",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.DUPLICATE_PROCESSING

    def test_condition_12_3_incorrect_currency(self) -> None:
        """Incorrect currency statement maps to 12.3."""
        case = _make_case(
            statement="The transaction was in the wrong currency",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.INCORRECT_CURRENCY

    def test_condition_12_4_incorrect_account(self) -> None:
        case = _make_case(
            statement="This was posted to the wrong account number",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.INCORRECT_ACCOUNT_NUMBER

    def test_condition_12_2_incorrect_code(self) -> None:
        case = _make_case(
            statement="The incorrect code was used for this transaction",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.INCORRECT_TRANSACTION_CODE

    def test_condition_12_7_invalid_data(self) -> None:
        case = _make_case(
            statement="Transaction contains invalid data",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.INVALID_DATA


# ============================================================================
# Category 13: Consumer Disputes
# ============================================================================


class TestConsumerDisputeCategorization:
    """Test Category 13 consumer dispute categorization."""

    def test_condition_13_1_not_received(self) -> None:
        """Merchandise not received statement maps to 13.1."""
        case = _make_case(
            statement="I ordered goods but they were never received",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.CONSUMER_DISPUTES
        assert result.condition == DisputeCondition.MERCHANDISE_NOT_RECEIVED

    def test_condition_13_1_did_not_arrive(self) -> None:
        case = _make_case(
            statement="My order did not arrive as expected",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.MERCHANDISE_NOT_RECEIVED

    def test_condition_13_2_cancelled_recurring(self) -> None:
        """Cancelled recurring transaction maps to 13.2."""
        case = _make_case(
            statement="I cancelled my subscription but was still charged",
            authorization_code="ABC",
            authorization_response_code="00",
            is_recurring=True,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.CANCELLED_RECURRING

    def test_condition_13_3_not_as_described(self) -> None:
        case = _make_case(
            statement="The product was not as described on the website",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.NOT_AS_DESCRIBED

    def test_condition_13_3_defective(self) -> None:
        case = _make_case(
            statement="The merchandise I received was defective",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.NOT_AS_DESCRIBED

    def test_condition_13_4_counterfeit(self) -> None:
        """'counterfeit' in statement triggers fraud detection first.
        Since fraud has priority, this categorizes as fraud (10.4) not consumer (13.4).
        To get 13.4, the statement must avoid fraud keywords."""
        case = _make_case(
            statement="I received counterfeit goods",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        # 'counterfeit' is a fraud indicator, so it routes to fraud category
        assert result.category == DisputeCategory.FRAUD

    def test_condition_13_4_fake(self) -> None:
        case = _make_case(
            statement="The product was fake and not genuine",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.COUNTERFEIT_MERCHANDISE

    def test_condition_13_5_misrepresentation(self) -> None:
        case = _make_case(
            statement="The merchant made false claims about the product",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.MISREPRESENTATION

    def test_condition_13_6_credit_not_processed(self) -> None:
        case = _make_case(
            statement="The merchant promised a refund not processed yet",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.CREDIT_NOT_PROCESSED

    def test_condition_13_7_cancelled_merchandise(self) -> None:
        case = _make_case(
            statement="I returned the merchandise but was not refunded",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.CANCELLED_MERCHANDISE

    def test_condition_13_8_oct_not_accepted(self) -> None:
        case = _make_case(
            statement="The original credit transaction was rejected",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.OCT_NOT_ACCEPTED

    def test_condition_13_9_atm_cash_not_received(self) -> None:
        """ATM transaction automatically maps to 13.9."""
        case = _make_case(
            statement="Cash was not dispensed at the ATM",
            authorization_code="ABC",
            authorization_response_code="00",
            environment=TransactionEnvironment.ATM,
        )
        result = categorize_dispute(case)
        assert result.condition == DisputeCondition.NON_RECEIPT_CASH_ATM
        assert result.confidence >= 0.90

    def test_default_consumer_dispute(self) -> None:
        """A vague statement with valid auth defaults to consumer dispute."""
        case = _make_case(
            statement="I have a problem with this transaction",
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.CONSUMER_DISPUTES


# ============================================================================
# Categorization hierarchy / priority
# ============================================================================


class TestCategorizationPriority:
    """Verify that the categorization priority hierarchy is respected."""

    def test_fraud_takes_priority_over_auth(self) -> None:
        """Fraud indicators override authorization indicators."""
        case = _make_case(
            statement="I did not authorize this - my card was declined",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            authorization_response_code="05",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_fraud_takes_priority_over_processing_error(self) -> None:
        """Fraud indicators override processing error indicators."""
        case = _make_case(
            statement="This is fraud - they charged the wrong amount",
            fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
            authorization_code="ABC",
            authorization_response_code="00",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.FRAUD

    def test_auth_takes_priority_over_consumer(self) -> None:
        """Authorization issues override consumer dispute indicators."""
        case = _make_case(
            statement="My card was declined but merchandise not received",
            authorization_response_code="05",
        )
        result = categorize_dispute(case)
        assert result.category == DisputeCategory.AUTHORIZATION

    def test_categorization_result_has_rationale(self) -> None:
        """Every categorization has a non-empty rationale."""
        case = _make_case(fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER)
        result = categorize_dispute(case)
        assert len(result.rationale) > 0

    def test_categorization_result_confidence_bounded(self) -> None:
        """Confidence score is always between 0 and 1."""
        case = _make_case(fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER)
        result = categorize_dispute(case)
        assert 0.0 <= result.confidence <= 1.0
