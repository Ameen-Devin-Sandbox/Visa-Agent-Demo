"""Comprehensive tests for the validity checking engine.

Tests all condition-specific validity checks from Visa Core Rules Section 11.7-11.10.
"""

from datetime import date

from src.models.dispute import CardholderInfo, DisputeCase, TransactionDetails
from src.models.enums import (
    DisputeCondition,
    Region,
    TransactionEnvironment,
)
from src.rules.validity import (
    check_condition_10_1_validity,
    check_condition_10_2_validity,
    check_condition_10_3_validity,
    check_condition_10_4_validity,
    check_condition_11_1_validity,
    check_condition_11_2_validity,
    check_condition_11_3_validity,
    check_condition_12_5_validity,
    check_condition_12_6_validity,
    check_condition_13_1_validity,
    check_condition_13_2_validity,
    check_condition_13_6_validity,
    check_dispute_validity,
    convert_to_rule_evaluation,
)


def _make_case(**txn_overrides: object) -> DisputeCase:
    defaults = {
        "transaction_id": "TXN-V-001",
        "transaction_date": date(2026, 2, 15),
        "processing_date": date(2026, 2, 16),
        "amount": 100.0,
        "currency": "USD",
        "merchant_name": "TestMerchant",
        "merchant_category_code": "5411",
        "merchant_country": "US",
        "acquirer_bin": "411111",
        "issuer_bin": "422222",
        "environment": TransactionEnvironment.ECOMMERCE,
        "region": Region.US,
    }
    defaults.update(txn_overrides)
    return DisputeCase(
        transaction=TransactionDetails(**defaults),
        cardholder=CardholderInfo(
            cardholder_name="Test User",
            partial_payment_credential="****1234",
        ),
    )


# ============================================================================
# 10.1 EMV Counterfeit Fraud
# ============================================================================


class TestCondition101Validity:
    """Validity checks for 10.1: EMV Liability Shift Counterfeit Fraud."""

    def test_valid_case(self) -> None:
        case = _make_case(environment=TransactionEnvironment.CARD_PRESENT)
        results = check_condition_10_1_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_chip_initiated(self) -> None:
        case = _make_case(
            environment=TransactionEnvironment.CARD_PRESENT,
            is_chip_initiated=True,
        )
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert len(invalid) >= 1
        assert any("Chip-initiated" in r.reason for r in invalid)

    def test_invalid_emergency_cash(self) -> None:
        case = _make_case(is_emergency_cash_disbursement=True)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Emergency Cash" in r.reason for r in invalid)

    def test_invalid_fallback(self) -> None:
        case = _make_case(is_fallback_transaction=True)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Fallback" in r.reason for r in invalid)

    def test_invalid_mobile_push(self) -> None:
        case = _make_case(is_mobile_push_payment=True)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Mobile Push" in r.reason for r in invalid)

    def test_invalid_cvv_not_verified(self) -> None:
        case = _make_case(cvv_present=True, cvv_verified=False)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("CVV" in r.reason for r in invalid)

    def test_invalid_cvv_none(self) -> None:
        """CVV present but verified is None → invalid."""
        case = _make_case(cvv_present=True, cvv_verified=None)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("CVV" in r.reason for r in invalid)

    def test_valid_cvv_verified(self) -> None:
        """CVV present and verified → valid."""
        case = _make_case(cvv_present=True, cvv_verified=True)
        results = check_condition_10_1_validity(case)
        # Should not have CVV-related invalidity
        cvv_invalid = [r for r in results if not r.is_valid and "CVV" in r.reason]
        assert len(cvv_invalid) == 0

    def test_invalid_token_non_europe(self) -> None:
        case = _make_case(is_token_transaction=True, region=Region.US)
        results = check_condition_10_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Token" in r.reason for r in invalid)

    def test_valid_token_europe(self) -> None:
        """Token transactions valid in Europe."""
        case = _make_case(is_token_transaction=True, region=Region.EUROPE)
        results = check_condition_10_1_validity(case)
        token_invalid = [r for r in results if not r.is_valid and "Token" in r.reason]
        assert len(token_invalid) == 0

    def test_rule_section_is_11_7_2_3(self) -> None:
        case = _make_case()
        results = check_condition_10_1_validity(case)
        assert all(r.rule_section == "11.7.2.3" for r in results)


# ============================================================================
# 10.2 EMV Non-Counterfeit Fraud
# ============================================================================


class TestCondition102Validity:
    """Validity checks for 10.2: EMV Non-Counterfeit Fraud."""

    def test_valid_case(self) -> None:
        case = _make_case(environment=TransactionEnvironment.CARD_PRESENT)
        results = check_condition_10_2_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_atm(self) -> None:
        case = _make_case(environment=TransactionEnvironment.ATM)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("ATM" in r.reason for r in invalid)

    def test_invalid_contactless(self) -> None:
        case = _make_case(is_contactless=True)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Contactless" in r.reason for r in invalid)

    def test_invalid_emergency_cash(self) -> None:
        case = _make_case(is_emergency_cash_disbursement=True)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Emergency Cash" in r.reason for r in invalid)

    def test_invalid_mobile_push(self) -> None:
        case = _make_case(is_mobile_push_payment=True)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Mobile Push" in r.reason for r in invalid)

    def test_invalid_veps(self) -> None:
        case = _make_case(is_veps_transaction=True)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("VEPS" in r.reason for r in invalid)

    def test_invalid_fallback(self) -> None:
        case = _make_case(is_fallback_transaction=True)
        results = check_condition_10_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Fallback" in r.reason for r in invalid)

    def test_rule_section_is_11_7_3_3(self) -> None:
        case = _make_case()
        results = check_condition_10_2_validity(case)
        assert all(r.rule_section == "11.7.3.3" for r in results)


# ============================================================================
# 10.3 Other Fraud - Card Present
# ============================================================================


class TestCondition103Validity:
    """Validity checks for 10.3: Other Fraud - Card-Present."""

    def test_valid_card_present(self) -> None:
        case = _make_case(environment=TransactionEnvironment.CARD_PRESENT)
        results = check_condition_10_3_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_not_card_present(self) -> None:
        case = _make_case(environment=TransactionEnvironment.ECOMMERCE)
        results = check_condition_10_3_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("not in Card-Present" in r.reason for r in invalid)

    def test_invalid_mobile_push(self) -> None:
        case = _make_case(
            environment=TransactionEnvironment.CARD_PRESENT,
            is_mobile_push_payment=True,
        )
        results = check_condition_10_3_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Mobile Push" in r.reason for r in invalid)


# ============================================================================
# 10.4 Other Fraud - Card Absent
# ============================================================================


class TestCondition104Validity:
    """Validity checks for 10.4: Other Fraud - Card-Absent."""

    def test_valid_ecommerce(self) -> None:
        case = _make_case(environment=TransactionEnvironment.ECOMMERCE)
        results = check_condition_10_4_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_card_present(self) -> None:
        case = _make_case(environment=TransactionEnvironment.CARD_PRESENT)
        results = check_condition_10_4_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("Card-Present" in r.reason for r in invalid)

    def test_invalid_3ds_non_europe(self) -> None:
        case = _make_case(
            three_d_secure_authenticated=True,
            region=Region.US,
        )
        results = check_condition_10_4_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("3-D Secure" in r.reason for r in invalid)

    def test_valid_3ds_europe(self) -> None:
        """3DS authenticated transactions are valid in Europe."""
        case = _make_case(
            three_d_secure_authenticated=True,
            region=Region.EUROPE,
        )
        results = check_condition_10_4_validity(case)
        tds_invalid = [r for r in results if not r.is_valid and "3-D Secure" in r.reason]
        assert len(tds_invalid) == 0


# ============================================================================
# 11.x Authorization conditions
# ============================================================================


class TestCondition111Validity:
    """Validity checks for 11.1: Card Recovery Bulletin."""

    def test_valid_case(self) -> None:
        case = _make_case()
        results = check_condition_11_1_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_mobile_push(self) -> None:
        case = _make_case(is_mobile_push_payment=True)
        results = check_condition_11_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert len(invalid) >= 1


class TestCondition112Validity:
    """Validity checks for 11.2: Declined Authorization."""

    def test_valid_declined(self) -> None:
        """Non-approved auth response code → valid dispute."""
        case = _make_case(authorization_response_code="14")
        results = check_condition_11_2_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_approved(self) -> None:
        """Authorization was approved (code starts with 0) → invalid dispute."""
        case = _make_case(authorization_response_code="00")
        results = check_condition_11_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("approved" in r.reason.lower() for r in invalid)

    def test_code_05_starts_with_0(self) -> None:
        """Response code 05 starts with '0' so auth is considered approved → invalid."""
        case = _make_case(authorization_response_code="05")
        results = check_condition_11_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert len(invalid) >= 1


class TestCondition113Validity:
    """Validity checks for 11.3: No Authorization."""

    def test_valid_no_auth(self) -> None:
        case = _make_case(authorization_code=None)
        results = check_condition_11_3_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_auth_exists(self) -> None:
        case = _make_case(authorization_code="ABC123")
        results = check_condition_11_3_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("authorization code exists" in r.reason.lower() for r in invalid)


# ============================================================================
# 12.x Processing Error conditions
# ============================================================================


class TestCondition125Validity:
    """Validity checks for 12.5: Incorrect Amount."""

    def test_valid_with_amount(self) -> None:
        case = _make_case()
        case.condition = DisputeCondition.INCORRECT_AMOUNT
        case.dispute_amount = 200.0
        results = check_condition_12_5_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_no_amount(self) -> None:
        case = _make_case()
        case.condition = DisputeCondition.INCORRECT_AMOUNT
        case.dispute_amount = None
        results = check_condition_12_5_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("No dispute amount" in r.reason for r in invalid)


class TestCondition126Validity:
    """Validity checks for 12.6: Duplicate Processing."""

    def test_always_valid(self) -> None:
        """12.6 has no specific invalid conditions in current implementation."""
        case = _make_case()
        results = check_condition_12_6_validity(case)
        assert all(r.is_valid for r in results)


# ============================================================================
# 13.x Consumer Dispute conditions
# ============================================================================


class TestCondition131Validity:
    """Validity checks for 13.1: Merchandise Not Received."""

    def test_valid_non_atm(self) -> None:
        case = _make_case(environment=TransactionEnvironment.ECOMMERCE)
        results = check_condition_13_1_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_atm(self) -> None:
        """ATM transactions should use 13.9 instead."""
        case = _make_case(environment=TransactionEnvironment.ATM)
        results = check_condition_13_1_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("ATM" in r.reason for r in invalid)


class TestCondition132Validity:
    """Validity checks for 13.2: Cancelled Recurring."""

    def test_valid_recurring(self) -> None:
        case = _make_case(is_recurring=True)
        results = check_condition_13_2_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_not_recurring(self) -> None:
        case = _make_case(is_recurring=False)
        results = check_condition_13_2_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("not a recurring" in r.reason.lower() for r in invalid)


class TestCondition136Validity:
    """Validity checks for 13.6: Credit Not Processed."""

    def test_valid_with_credits(self) -> None:
        case = _make_case()
        case.prior_credits = [{"amount": 50.0}]
        results = check_condition_13_6_validity(case)
        assert all(r.is_valid for r in results)

    def test_invalid_no_credits(self) -> None:
        case = _make_case()
        case.prior_credits = []
        results = check_condition_13_6_validity(case)
        invalid = [r for r in results if not r.is_valid]
        assert any("No evidence" in r.reason for r in invalid)


# ============================================================================
# Main dispatcher: check_dispute_validity
# ============================================================================


class TestCheckDisputeValidity:
    """Test the main validity checking dispatcher."""

    def test_no_condition_is_invalid(self) -> None:
        case = _make_case()
        case.condition = None
        results = check_dispute_validity(case)
        assert not results[0].is_valid
        assert "No dispute condition" in results[0].reason

    def test_dispatches_to_10_1(self) -> None:
        case = _make_case()
        case.condition = DisputeCondition.EMV_COUNTERFEIT_FRAUD
        results = check_dispute_validity(case)
        assert all(r.rule_section == "11.7.2.3" for r in results)

    def test_dispatches_to_10_4(self) -> None:
        case = _make_case()
        case.condition = DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        results = check_dispute_validity(case)
        assert all(r.rule_section == "11.7.5.3" for r in results)

    def test_unknown_condition_default_valid(self) -> None:
        """Conditions without a specific checker default to valid."""
        case = _make_case()
        case.condition = DisputeCondition.NOT_AS_DESCRIBED
        results = check_dispute_validity(case)
        assert results[0].is_valid
        assert "default valid" in results[0].reason

    def test_convert_to_rule_evaluation(self) -> None:
        case = _make_case()
        case.condition = DisputeCondition.EMV_COUNTERFEIT_FRAUD
        results = check_dispute_validity(case)
        eval_result = convert_to_rule_evaluation(results[0])
        assert eval_result.rule_id.startswith("validity_")
        assert eval_result.rule_section == results[0].rule_section
