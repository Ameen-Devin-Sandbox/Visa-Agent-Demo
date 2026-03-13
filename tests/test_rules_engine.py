"""Tests for the rule engine — the core of the system."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.models.dispute import Dispute, Party, TransactionDetail
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    FraudType,
    PartyRole,
    TransactionEnvironment,
)
from src.rules.engine import RuleEngine
from src.rules.registry import (
    ALL_CONDITIONS,
    COMPELLING_EVIDENCE,
    CONDITIONS_BY_CATEGORY,
    CONDITIONS_BY_CODE,
    get_compelling_evidence_for_condition,
    get_condition_rule,
)


def make_dispute(
    condition: DisputeCondition | None = None,
    category: DisputeCategory | None = None,
    environment: TransactionEnvironment = TransactionEnvironment.ECOMMERCE,
    processing_date: date | None = None,
    amount: Decimal = Decimal("100.00"),
    fraud_reported: bool = False,
    fraud_type: FraudType | None = None,
    financial_loss: bool = True,
    cardholder_attempted: bool = False,
    is_mobile_push: bool = False,
    is_stp: bool = False,
    is_emergency_cash: bool = False,
    disputes_on_account: int = 0,
    eci: str | None = None,
    cavv: bool = False,
    three_ds: bool = False,
    cvv2_result: str | None = None,
    cvv2_presence: str | None = None,
) -> Dispute:
    """Helper to create a dispute for testing."""
    proc_date = processing_date or (date.today() - timedelta(days=30))
    return Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-TEST-001",
            transaction_date=proc_date - timedelta(days=1),
            processing_date=proc_date,
            amount=amount,
            currency="USD",
            merchant_name="Test Merchant",
            merchant_category_code="5411",
            environment=environment,
            fraud_type_reported=fraud_type,
            is_mobile_push_payment=is_mobile_push,
            is_straight_through_processing=is_stp,
            is_emergency_cash=is_emergency_cash,
            eci_indicator=eci,
            cavv_present=cavv,
            three_ds_authenticated=three_ds,
            cvv2_result=cvv2_result,
            cvv2_presence_indicator=cvv2_presence,
        ),
        category=category,
        condition=condition,
        issuer=Party(role=PartyRole.ISSUER, name="Test Issuer"),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Test Acquirer"),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Test Cardholder"),
        merchant=Party(role=PartyRole.MERCHANT, name="Test Merchant"),
        fraud_reported_to_visa=fraud_reported,
        fraud_type=fraud_type,
        cardholder_financial_loss=financial_loss,
        cardholder_attempted_resolution=cardholder_attempted,
        disputes_on_account_last_120_days=disputes_on_account,
    )


# ── Registry Tests ───────────────────────────────────────────────────────────


class TestRegistry:
    def test_all_conditions_loaded(self):
        """All 23 dispute conditions are registered."""
        assert len(ALL_CONDITIONS) == 23

    def test_conditions_by_code(self):
        assert DisputeCondition.FRAUD_CARD_ABSENT in CONDITIONS_BY_CODE
        assert DisputeCondition.CONSUMER_NOT_RECEIVED in CONDITIONS_BY_CODE

    def test_conditions_by_category(self):
        assert len(CONDITIONS_BY_CATEGORY[DisputeCategory.FRAUD]) == 5
        assert len(CONDITIONS_BY_CATEGORY[DisputeCategory.AUTHORIZATION]) == 3
        assert len(CONDITIONS_BY_CATEGORY[DisputeCategory.PROCESSING_ERRORS]) == 6
        assert len(CONDITIONS_BY_CATEGORY[DisputeCategory.CONSUMER_DISPUTES]) == 9

    def test_get_condition_rule(self):
        rule = get_condition_rule(DisputeCondition.FRAUD_CARD_ABSENT)
        assert rule.name == "Other Fraud — Card-Absent Environment"
        assert rule.rule_section == "11.7.5"
        assert rule.time_limit.calendar_days == 120

    def test_get_condition_rule_unknown(self):
        with pytest.raises(ValueError):
            get_condition_rule("99.99")  # type: ignore

    def test_compelling_evidence_count(self):
        assert len(COMPELLING_EVIDENCE) == 16

    def test_compelling_evidence_for_10_4(self):
        ce = get_compelling_evidence_for_condition(DisputeCondition.FRAUD_CARD_ABSENT)
        assert len(ce) >= 14  # Most CE items apply to 10.4

    def test_compelling_evidence_for_11_1(self):
        """Authorization conditions have no compelling evidence."""
        ce = get_compelling_evidence_for_condition(DisputeCondition.AUTH_CARD_RECOVERY)
        assert len(ce) == 0


# ── Rule Engine Tests ────────────────────────────────────────────────────────


class TestRuleEngine:
    def setup_method(self):
        self.engine = RuleEngine()

    # Eligibility tests

    def test_eligible_fraud_card_absent(self):
        """Basic fraud card-absent dispute should be eligible."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            environment=TransactionEnvironment.ECOMMERCE,
            fraud_reported=True,
            fraud_type=FraudType.CARD_ABSENT,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is True
        assert result.condition == DisputeCondition.FRAUD_CARD_ABSENT

    def test_ineligible_no_condition(self):
        """Dispute without a condition code should be ineligible."""
        dispute = make_dispute(condition=None)
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False

    def test_ineligible_no_financial_loss(self):
        """Dispute without cardholder financial loss should be ineligible."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            financial_loss=False,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False
        assert any("financial loss" in r.lower() for r in result.blocking_reasons)

    def test_ineligible_fraud_not_reported(self):
        """Fraud dispute without fraud reporting should be ineligible."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=False,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False
        assert any("fraud" in r.lower() for r in result.blocking_reasons)

    def test_ineligible_mobile_push_payment(self):
        """Mobile Push Payment is invalid for most conditions."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            is_mobile_push=True,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False
        assert any("mobile push" in r.lower() for r in result.blocking_reasons)

    def test_ineligible_emergency_cash(self):
        """Emergency Cash Disbursement is invalid for 10.4."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            is_emergency_cash=True,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False

    def test_ineligible_stp(self):
        """Straight Through Processing is invalid for 10.4."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            is_stp=True,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False

    def test_ineligible_35_dispute_cap(self):
        """More than 35 disputes in 120 days makes 10.4 invalid."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            disputes_on_account=36,
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False
        assert any("35" in r for r in result.blocking_reasons)

    def test_ineligible_expired_time_limit(self):
        """Dispute filed after time limit should be ineligible."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            processing_date=date.today() - timedelta(days=130),  # >120 days
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is False
        assert any("expired" in r.lower() for r in result.blocking_reasons)

    def test_eligible_within_time_limit(self):
        """Dispute within time limit should be eligible."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            category=DisputeCategory.FRAUD,
            fraud_reported=True,
            processing_date=date.today() - timedelta(days=60),
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert result.eligible is True

    def test_authorization_no_financial_loss_ok(self):
        """Authorization category doesn't require cardholder financial loss."""
        dispute = make_dispute(
            condition=DisputeCondition.AUTH_DECLINED,
            category=DisputeCategory.AUTHORIZATION,
            financial_loss=False,
        )
        result = self.engine.evaluate_eligibility(dispute)
        # Should NOT block for financial loss
        assert not any("financial loss" in r.lower() for r in result.blocking_reasons)

    def test_consumer_not_received_wait_period(self):
        """Consumer not-received has a 15-day wait period warning."""
        dispute = make_dispute(
            condition=DisputeCondition.CONSUMER_NOT_RECEIVED,
            category=DisputeCategory.CONSUMER_DISPUTES,
            cardholder_attempted=True,
            processing_date=date.today() - timedelta(days=10),  # within 15-day wait
        )
        result = self.engine.evaluate_eligibility(dispute)
        assert any("wait" in w.lower() for w in result.warnings)

    # Deadline tests

    def test_deadline_120_days(self):
        """Fraud conditions have 120-day deadline."""
        dispute = make_dispute(
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            processing_date=date(2025, 1, 1),
        )
        result = self.engine.calculate_deadlines(dispute)
        assert result.dispute_deadline == date(2025, 1, 1) + timedelta(days=120)

    def test_deadline_75_days(self):
        """Authorization conditions have 75-day deadline."""
        dispute = make_dispute(
            condition=DisputeCondition.AUTH_DECLINED,
            processing_date=date(2025, 1, 1),
        )
        result = self.engine.calculate_deadlines(dispute)
        assert result.dispute_deadline == date(2025, 1, 1) + timedelta(days=75)

    def test_deadline_540_day_cap(self):
        """Consumer conditions with extended dates are capped at 540 days."""
        dispute = make_dispute(
            condition=DisputeCondition.CONSUMER_NOT_RECEIVED,
            processing_date=date(2024, 1, 1),
        )
        result = self.engine.calculate_deadlines(dispute)
        max_date = date(2024, 1, 1) + timedelta(days=540)
        assert result.max_absolute_deadline == max_date

    # Condition determination tests

    def test_determine_fraud_card_absent(self):
        """Should identify 10.4 for e-commerce fraud."""
        dispute = make_dispute(
            environment=TransactionEnvironment.ECOMMERCE,
            fraud_type=FraudType.CARD_ABSENT,
        )
        dispute.category = None  # Force full evaluation
        candidates = self.engine.determine_condition(dispute)
        conditions = [c for c, _, _ in candidates]
        assert DisputeCondition.FRAUD_CARD_ABSENT in conditions

    def test_determine_auth_declined(self):
        """Should identify 11.2 for declined authorization."""
        dispute = make_dispute(environment=TransactionEnvironment.CARD_PRESENT)
        dispute.transaction.authorization_response = "Decline-51"
        dispute.category = None
        candidates = self.engine.determine_condition(dispute)
        conditions = [c for c, _, _ in candidates]
        assert DisputeCondition.AUTH_DECLINED in conditions

    # Flow type tests

    def test_fraud_uses_pre_arb_flow(self):
        """Fraud (Cat 10) uses pre-arb flow, not dispute response."""
        dispute = make_dispute(category=DisputeCategory.FRAUD)
        assert dispute.uses_dispute_response_flow is False

    def test_consumer_uses_dispute_response_flow(self):
        """Consumer (Cat 13) uses dispute response flow."""
        dispute = make_dispute(category=DisputeCategory.CONSUMER_DISPUTES)
        assert dispute.uses_dispute_response_flow is True

    # Documentation tests

    def test_get_required_docs_fraud(self):
        """Fraud card-absent requires cardholder certification."""
        dispute = make_dispute(condition=DisputeCondition.FRAUD_CARD_ABSENT)
        docs = self.engine.get_required_documentation(dispute)
        assert any("cardholder" in d.lower() for d in docs)

    def test_get_compelling_evidence_10_4(self):
        """Should return CE items for 10.4."""
        dispute = make_dispute(condition=DisputeCondition.FRAUD_CARD_ABSENT)
        ce = self.engine.get_compelling_evidence_options(dispute)
        assert len(ce) >= 14

    # VFMP special case

    def test_vfmp_no_invalid_conditions(self):
        """10.5 VFMP has no invalid conditions."""
        rule = get_condition_rule(DisputeCondition.FRAUD_VFMP)
        assert len(rule.invalid_conditions) == 0

    def test_vfmp_time_limit_from_report(self):
        """10.5 time limit is from VFMP report date, not transaction date."""
        rule = get_condition_rule(DisputeCondition.FRAUD_VFMP)
        assert rule.time_limit.from_event == "vfmp_report_date"

    # Invalid condition details

    def test_10_4_has_most_invalid_conditions(self):
        """10.4 should have the most invalid conditions."""
        rule_10_4 = get_condition_rule(DisputeCondition.FRAUD_CARD_ABSENT)
        all_counts = {
            rule.condition: len(rule.invalid_conditions) for rule in ALL_CONDITIONS
        }
        assert len(rule_10_4.invalid_conditions) == max(all_counts.values())

    # Amount rules

    def test_12_2_double_amount(self):
        """12.2 has a DOUBLE amount rule for credit<>debit swap."""
        rule = get_condition_rule(DisputeCondition.PROC_INCORRECT_CODE)
        assert "double" in rule.dispute_amount_rule.lower()

    def test_12_5_difference_amount(self):
        """12.5 limits dispute to the difference between amounts."""
        rule = get_condition_rule(DisputeCondition.PROC_INCORRECT_AMOUNT)
        assert "difference" in rule.dispute_amount_rule.lower()
