"""Rule engine — evaluates Visa dispute rules against case data.

This is NOT a RAG system. It programmatically evaluates encoded rules against
dispute case data to produce deterministic decisions where possible, and
structured context for LLM reasoning where judgment is needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from src.models.dispute import Dispute
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    FraudType,
    TransactionEnvironment,
)
from src.rules.models import DisputeConditionRule, InvalidCondition
from src.rules.registry import (
    get_compelling_evidence_for_condition,
    get_condition_rule,
)

logger = logging.getLogger(__name__)


@dataclass
class EligibilityResult:
    """Result of evaluating whether a dispute is eligible to be filed."""

    eligible: bool = False
    condition: DisputeCondition | None = None
    reasons: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deadline: date | None = None
    wait_until: date | None = None
    required_documentation: list[str] = field(default_factory=list)
    max_dispute_amount: Decimal | None = None
    rule_references: list[str] = field(default_factory=list)


@dataclass
class DeadlineResult:
    """Calculated deadlines for a dispute."""

    dispute_deadline: date
    wait_until: date | None = None
    pre_arb_deadline: date | None = None
    arbitration_deadline: date | None = None
    max_absolute_deadline: date | None = None
    description: str = ""


class RuleEngine:
    """Evaluates Visa dispute rules against case data."""

    def evaluate_eligibility(self, dispute: Dispute) -> EligibilityResult:
        """Evaluate whether a dispute is eligible to be filed.

        Checks in order:
        1. Financial loss prerequisite
        2. Condition-specific prerequisites
        3. Invalid dispute conditions
        4. Time limits
        5. Wait periods
        6. Documentation requirements
        """
        if dispute.condition is None:
            return EligibilityResult(
                eligible=False,
                blocking_reasons=["No dispute condition specified — must determine condition first"],
            )

        rule = get_condition_rule(dispute.condition)
        result = EligibilityResult(condition=dispute.condition)
        result.rule_references.append(f"Section {rule.rule_section}")

        self._check_financial_loss(dispute, rule, result)
        self._check_prerequisites(dispute, rule, result)
        self._check_invalid_conditions(dispute, rule, result)
        self._check_time_limits(dispute, rule, result)
        self._check_documentation(dispute, rule, result)

        result.eligible = len(result.blocking_reasons) == 0
        return result

    def determine_condition(self, dispute: Dispute) -> list[tuple[DisputeCondition, float, str]]:
        """Determine applicable dispute conditions based on case facts.

        Returns a ranked list of (condition, confidence, reasoning) tuples.
        """
        candidates: list[tuple[DisputeCondition, float, str]] = []

        # Fraud category: cardholder denies authorization/participation
        if dispute.is_fraud_category or dispute.category is None:
            candidates.extend(self._evaluate_fraud_conditions(dispute))

        # Authorization category
        if dispute.is_authorization_category or dispute.category is None:
            candidates.extend(self._evaluate_auth_conditions(dispute))

        # Processing errors
        if dispute.category in (DisputeCategory.PROCESSING_ERRORS, None):
            candidates.extend(self._evaluate_processing_conditions(dispute))

        # Consumer disputes
        if dispute.category in (DisputeCategory.CONSUMER_DISPUTES, None):
            candidates.extend(self._evaluate_consumer_conditions(dispute))

        candidates.sort(key=lambda c: c[1], reverse=True)
        return candidates

    def calculate_deadlines(self, dispute: Dispute, reference_date: date | None = None) -> DeadlineResult:
        """Calculate all relevant deadlines for a dispute."""
        if dispute.condition is None:
            raise ValueError("Cannot calculate deadlines without a dispute condition")

        rule = get_condition_rule(dispute.condition)
        tl = rule.time_limit
        ref = reference_date or dispute.transaction.processing_date

        dispute_deadline = ref + timedelta(days=tl.calendar_days)
        wait_until = None
        if tl.wait_days_before > 0:
            wait_until = ref + timedelta(days=tl.wait_days_before)

        max_absolute = None
        if tl.max_calendar_days:
            max_absolute = dispute.transaction.processing_date + timedelta(days=tl.max_calendar_days)
            dispute_deadline = min(dispute_deadline, max_absolute)

        # Pre-arb: 30 calendar days from dispute or dispute response processing date
        pre_arb_deadline = None
        if dispute.last_processing_date:
            pre_arb_deadline = dispute.last_processing_date + timedelta(days=30)

        return DeadlineResult(
            dispute_deadline=dispute_deadline,
            wait_until=wait_until,
            pre_arb_deadline=pre_arb_deadline,
            arbitration_deadline=(
                dispute.last_processing_date + timedelta(days=10)
                if dispute.last_processing_date
                else None
            ),
            max_absolute_deadline=max_absolute,
            description=tl.description,
        )

    def check_invalid_conditions(self, dispute: Dispute) -> list[tuple[InvalidCondition, bool, str]]:
        """Check each invalid condition for the dispute.

        Returns list of (condition, is_triggered, explanation).
        """
        if dispute.condition is None:
            return []

        rule = get_condition_rule(dispute.condition)
        results: list[tuple[InvalidCondition, bool, str]] = []

        for inv in rule.invalid_conditions:
            triggered, explanation = self._evaluate_invalid_condition(dispute, inv)
            results.append((inv, triggered, explanation))

        return results

    def get_required_documentation(self, dispute: Dispute) -> list[str]:
        """Get list of required documentation for the dispute condition."""
        if dispute.condition is None:
            return []
        rule = get_condition_rule(dispute.condition)
        docs = []
        for doc_req in rule.documentation_requirements:
            if doc_req.is_mandatory:
                docs.append(f"[REQUIRED] {doc_req.description}")
            else:
                docs.append(f"[OPTIONAL] {doc_req.description} — {doc_req.condition_notes}")
        return docs

    def get_compelling_evidence_options(self, dispute: Dispute) -> list[str]:
        """Get available compelling evidence types for this dispute condition."""
        if dispute.condition is None:
            return []
        ce_items = get_compelling_evidence_for_condition(dispute.condition)
        return [f"CE #{ce.item_number}: {ce.description}" for ce in ce_items]

    # ── Private evaluation methods ───────────────────────────────────────

    def _check_financial_loss(
        self, dispute: Dispute, rule: DisputeConditionRule, result: EligibilityResult
    ) -> None:
        """Check financial loss prerequisite (Section 1.10.1.1)."""
        # Authorization category: Issuer must have suffered loss (not cardholder)
        # 12.4 and 13.8: exempt from cardholder financial loss requirement
        exempt_conditions = {DisputeCondition.PROC_INCORRECT_ACCOUNT, DisputeCondition.CONSUMER_OCT_NOT_ACCEPTED}
        is_auth = dispute.condition and dispute.condition.category == DisputeCategory.AUTHORIZATION

        if not is_auth and dispute.condition not in exempt_conditions:
            if not dispute.cardholder_financial_loss:
                result.blocking_reasons.append(
                    "Cardholder has not suffered financial loss (required per Section 1.10.1.1, "
                    "except for Category 11 Authorization, 12.4, and 13.8)"
                )

    def _check_prerequisites(
        self, dispute: Dispute, rule: DisputeConditionRule, result: EligibilityResult
    ) -> None:
        """Check condition-specific prerequisites."""
        for prereq in rule.prerequisites:
            # Fraud reporting check
            if "report Fraud Activity" in prereq and not dispute.fraud_reported_to_visa:
                result.blocking_reasons.append(
                    f"Prerequisite not met: {prereq} — Fraud not yet reported to Visa"
                )
            # Merchant resolution attempt check
            elif "attempt to resolve" in prereq.lower() and not dispute.cardholder_attempted_resolution:
                result.blocking_reasons.append(
                    f"Prerequisite not met: {prereq} — Cardholder has not attempted resolution with Merchant"
                )
            else:
                result.reasons.append(f"Prerequisite met: {prereq}")

    def _check_invalid_conditions(
        self, dispute: Dispute, rule: DisputeConditionRule, result: EligibilityResult
    ) -> None:
        """Check invalid dispute conditions."""
        for inv in rule.invalid_conditions:
            triggered, explanation = self._evaluate_invalid_condition(dispute, inv)
            if triggered:
                result.blocking_reasons.append(
                    f"INVALID DISPUTE [{inv.condition_id}]: {inv.description} — {explanation}"
                )

    def _evaluate_invalid_condition(
        self, dispute: Dispute, inv: InvalidCondition
    ) -> tuple[bool, str]:
        """Evaluate a single invalid condition. Returns (triggered, explanation)."""
        txn = dispute.transaction

        if inv.check_field is None:
            return False, "Requires manual/LLM evaluation"

        # Get the value from transaction or dispute
        val = None
        if hasattr(txn, inv.check_field):
            val = getattr(txn, inv.check_field)
        elif hasattr(dispute, inv.check_field):
            val = getattr(dispute, inv.check_field)
        else:
            return False, f"Field '{inv.check_field}' not found on transaction or dispute"

        if inv.check_logic == "equals":
            triggered = str(val) == inv.check_value
        elif inv.check_logic == "greater_than":
            try:
                triggered = float(val) > float(inv.check_value or 0)
            except (ValueError, TypeError):
                triggered = False
        elif inv.check_logic == "contains":
            triggered = inv.check_value in str(val) if inv.check_value else False
        else:
            return False, "Custom logic — requires LLM evaluation"

        if triggered:
            return True, f"{inv.check_field}={val} matches invalid condition"
        return False, f"{inv.check_field}={val} does not trigger"

    def _check_time_limits(
        self, dispute: Dispute, rule: DisputeConditionRule, result: EligibilityResult
    ) -> None:
        """Check time limits for dispute filing."""
        today = date.today()
        tl = rule.time_limit
        ref = dispute.transaction.processing_date

        deadline = ref + timedelta(days=tl.calendar_days)
        if tl.max_calendar_days:
            max_deadline = ref + timedelta(days=tl.max_calendar_days)
            deadline = min(deadline, max_deadline)
            result.max_dispute_amount  # just accessing to be safe

        result.deadline = deadline

        if today > deadline:
            result.blocking_reasons.append(
                f"Time limit EXPIRED: deadline was {deadline} ({tl.calendar_days} cal days from {ref}). "
                f"Today is {today}."
            )
        else:
            days_remaining = (deadline - today).days
            result.reasons.append(f"Within time limit: {days_remaining} days remaining (deadline: {deadline})")
            if days_remaining <= 7:
                result.warnings.append(f"URGENT: Only {days_remaining} days remaining to file")

        if tl.wait_days_before > 0:
            wait_until = ref + timedelta(days=tl.wait_days_before)
            result.wait_until = wait_until
            if today < wait_until:
                result.warnings.append(
                    f"Must wait until {wait_until} ({tl.wait_days_before} cal days from {ref}) before filing"
                )

    def _check_documentation(
        self, dispute: Dispute, rule: DisputeConditionRule, result: EligibilityResult
    ) -> None:
        """Check if required documentation is provided."""
        provided_types = {doc.document_type for doc in dispute.evidence}
        for doc_req in rule.documentation_requirements:
            if doc_req.is_mandatory and doc_req.document_type not in provided_types:
                result.required_documentation.append(doc_req.description)
                result.warnings.append(f"Missing required document: {doc_req.description}")

    # ── Condition evaluation methods ─────────────────────────────────────

    def _evaluate_fraud_conditions(
        self, dispute: Dispute
    ) -> list[tuple[DisputeCondition, float, str]]:
        """Evaluate which fraud conditions match the dispute facts."""
        results = []
        txn = dispute.transaction

        # 10.1: EMV Counterfeit — card-present, chip card, not at chip-reading device
        if (
            txn.environment == TransactionEnvironment.CARD_PRESENT
            and txn.fraud_type_reported == FraudType.COUNTERFEIT
        ):
            confidence = 0.9 if not txn.is_chip_reading_device else 0.3
            results.append((DisputeCondition.FRAUD_EMV_COUNTERFEIT, confidence, "Counterfeit fraud, card-present"))

        # 10.2: EMV Non-Counterfeit — card-present, lost/stolen/NRI
        if (
            txn.environment == TransactionEnvironment.CARD_PRESENT
            and txn.fraud_type_reported in (FraudType.LOST, FraudType.STOLEN, FraudType.NOT_RECEIVED_AS_ISSUED)
        ):
            confidence = 0.85
            results.append((DisputeCondition.FRAUD_EMV_NON_COUNTERFEIT, confidence, "Non-counterfeit fraud (lost/stolen/NRI), card-present"))

        # 10.3: Other Fraud Card-Present — key-entered
        if txn.environment == TransactionEnvironment.CARD_PRESENT and txn.pos_entry_mode == "01":
            confidence = 0.8
            results.append((DisputeCondition.FRAUD_CARD_PRESENT, confidence, "Key-entered card-present fraud"))

        # 10.4: Other Fraud Card-Absent
        if txn.environment in (
            TransactionEnvironment.CARD_ABSENT,
            TransactionEnvironment.ECOMMERCE,
            TransactionEnvironment.MAIL_PHONE,
        ):
            confidence = 0.9
            results.append((DisputeCondition.FRAUD_CARD_ABSENT, confidence, "Card-absent fraud"))

        return results

    def _evaluate_auth_conditions(
        self, dispute: Dispute
    ) -> list[tuple[DisputeCondition, float, str]]:
        """Evaluate authorization conditions."""
        results = []
        txn = dispute.transaction

        # 11.2: Declined Authorization
        if txn.authorization_response and txn.authorization_response.startswith("Decline"):
            results.append((DisputeCondition.AUTH_DECLINED, 0.9, "Authorization was declined but transaction completed"))

        # 11.3: No Auth / Late Presentment
        if txn.authorization_code is None:
            results.append((DisputeCondition.AUTH_NO_AUTH_LATE, 0.7, "No authorization code present"))

        return results

    def _evaluate_processing_conditions(
        self, dispute: Dispute
    ) -> list[tuple[DisputeCondition, float, str]]:
        """Evaluate processing error conditions."""
        results = []
        txn = dispute.transaction

        if txn.is_dcc:
            results.append((DisputeCondition.PROC_INCORRECT_CURRENCY, 0.7, "DCC transaction"))

        return results

    def _evaluate_consumer_conditions(
        self, dispute: Dispute
    ) -> list[tuple[DisputeCondition, float, str]]:
        """Evaluate consumer dispute conditions."""
        results = []
        txn = dispute.transaction

        if txn.is_recurring:
            results.append((DisputeCondition.CONSUMER_CANCELLED_RECURRING, 0.6, "Recurring transaction"))

        if txn.environment == TransactionEnvironment.ATM:
            results.append((DisputeCondition.CONSUMER_ATM_NON_RECEIPT, 0.5, "ATM transaction"))

        return results
