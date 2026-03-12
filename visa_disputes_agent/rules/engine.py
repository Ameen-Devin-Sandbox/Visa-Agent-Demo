"""Central rules engine that provides unified access to all dispute rules."""

from __future__ import annotations

from datetime import date

import structlog

from visa_disputes_agent.models.dispute import (
    DisputeTask,
    RuleEvaluationResult,
    TimeLimitResult,
)
from visa_disputes_agent.models.enums import (
    DisputeCategory,
    DisputeCondition,
    Region,
)
from visa_disputes_agent.rules.authorization_rules import AuthorizationDisputeRules
from visa_disputes_agent.rules.base import (
    CompellingEvidenceItem,
    DisputeReasonRule,
    DisputeResponseRequirement,
    DisputeRuleSet,
    DocumentationRequirement,
    InvalidDisputeRule,
    TimeLimitRule,
)
from visa_disputes_agent.rules.consumer_dispute_rules import ConsumerDisputeRules
from visa_disputes_agent.rules.fraud_rules import FraudDisputeRules
from visa_disputes_agent.rules.processing_error_rules import ProcessingErrorDisputeRules

logger = structlog.get_logger()


class RulesEngine:
    """Central engine that provides access to all Visa dispute rules.

    This is NOT a RAG system. Rules are encoded as structured Python data
    with explicit logic for evaluation. The engine applies deterministic
    rule matching against dispute tasks.
    """

    def __init__(self) -> None:
        self._rule_sets: dict[DisputeCategory, DisputeRuleSet] = {
            DisputeCategory.FRAUD: FraudDisputeRules(),
            DisputeCategory.AUTHORIZATION: AuthorizationDisputeRules(),
            DisputeCategory.PROCESSING_ERRORS: ProcessingErrorDisputeRules(),
            DisputeCategory.CONSUMER_DISPUTES: ConsumerDisputeRules(),
        }
        self._condition_to_category: dict[DisputeCondition, DisputeCategory] = {}
        self._build_condition_index()
        logger.info("rules_engine_initialized", categories=len(self._rule_sets))

    def _build_condition_index(self) -> None:
        """Build reverse index from condition to category."""
        for category, rule_set in self._rule_sets.items():
            for condition in rule_set.conditions:
                self._condition_to_category[condition] = category

    def get_rule_set(self, category: DisputeCategory) -> DisputeRuleSet:
        """Get the rule set for a dispute category."""
        return self._rule_sets[category]

    def get_category_for_condition(self, condition: DisputeCondition) -> DisputeCategory:
        """Look up which category a dispute condition belongs to."""
        return self._condition_to_category[condition]

    def classify_dispute(self, task: DisputeTask) -> DisputeCondition | None:
        """Attempt to classify a dispute into a specific condition.

        Uses transaction attributes and dispute details to determine the
        most likely dispute condition. Returns None if classification
        cannot be determined automatically.
        """
        if task.dispute_condition is not None:
            return task.dispute_condition

        # Classification logic based on transaction characteristics
        txn = task.transaction

        if task.dispute_category == DisputeCategory.FRAUD:
            return self._classify_fraud(task)
        elif task.dispute_category == DisputeCategory.AUTHORIZATION:
            return self._classify_authorization(task)
        elif task.dispute_category == DisputeCategory.PROCESSING_ERRORS:
            return self._classify_processing_error(task)
        elif task.dispute_category == DisputeCategory.CONSUMER_DISPUTES:
            return self._classify_consumer_dispute(task)

        # If no category specified, try to infer from transaction details
        if not txn.was_authorized:
            return DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT

        logger.warning("dispute_classification_failed", task_id=str(task.task_id))
        return None

    def _classify_fraud(self, task: DisputeTask) -> DisputeCondition:
        """Classify a fraud dispute into a specific condition."""
        txn = task.transaction
        if txn.is_chip_transaction and not txn.is_chip_reading_device:
            return DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT
        if txn.environment in {
            task.transaction.environment.CARD_ABSENT,
            task.transaction.environment.ECOMMERCE,
            task.transaction.environment.MAIL_PHONE,
            task.transaction.environment.RECURRING,
        }:
            return DisputeCondition.OTHER_FRAUD_CARD_ABSENT
        return DisputeCondition.OTHER_FRAUD_CARD_PRESENT

    def _classify_authorization(self, task: DisputeTask) -> DisputeCondition:
        """Classify an authorization dispute into a specific condition."""
        txn = task.transaction
        if txn.authorization_response_code in {"04", "07", "41", "43"}:
            return DisputeCondition.CARD_RECOVERY_BULLETIN
        if not txn.was_authorized:
            return DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT
        return DisputeCondition.DECLINED_AUTHORIZATION

    def _classify_processing_error(self, task: DisputeTask) -> DisputeCondition:
        """Classify a processing error dispute into a specific condition."""
        reason = task.dispute_reason.lower()
        if "duplicate" in reason:
            return DisputeCondition.DUPLICATE_PROCESSING
        if "amount" in reason:
            return DisputeCondition.INCORRECT_AMOUNT
        if "currency" in reason:
            return DisputeCondition.INCORRECT_CURRENCY
        if "account" in reason:
            return DisputeCondition.INCORRECT_ACCOUNT_NUMBER
        if "late" in reason or "presentment" in reason:
            return DisputeCondition.LATE_PRESENTMENT
        if "paid" in reason or "other means" in reason:
            return DisputeCondition.PAID_BY_OTHER_MEANS
        return DisputeCondition.INCORRECT_TRANSACTION_CODE

    def _classify_consumer_dispute(self, task: DisputeTask) -> DisputeCondition:
        """Classify a consumer dispute into a specific condition."""
        reason = task.dispute_reason.lower()
        if "not received" in reason and "cash" in reason and "atm" in reason:
            return DisputeCondition.NON_RECEIPT_OF_CASH_ATM
        if "not received" in reason:
            return DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED
        if "not as described" in reason or "different" in reason:
            return DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED
        if "counterfeit" in reason:
            return DisputeCondition.COUNTERFEIT_MERCHANDISE
        if "cancel" in reason and "recurring" in reason:
            return DisputeCondition.CANCELLED_RECURRING
        if "cancel" in reason or "return" in reason:
            return DisputeCondition.CANCELLED_MERCHANDISE_SERVICES
        if "defective" in reason:
            return DisputeCondition.DEFECTIVE_MERCHANDISE
        if "credit transaction" in reason:
            return DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED
        return DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED

    def check_dispute_validity(
        self, task: DisputeTask, condition: DisputeCondition
    ) -> list[RuleEvaluationResult]:
        """Check if a dispute is valid by evaluating it against invalid dispute rules.

        Returns a list of rule evaluation results. If any rule is satisfied
        (meaning an invalid condition matches), the dispute is invalid.
        """
        category = self.get_category_for_condition(condition)
        rule_set = self.get_rule_set(category)
        invalid_rules = rule_set.get_invalid_dispute_rules(condition)
        results: list[RuleEvaluationResult] = []

        for rule in invalid_rules:
            is_invalid = self._evaluate_invalid_rule(task, rule)
            results.append(
                RuleEvaluationResult(
                    rule_id=f"invalid_{condition.value}_{len(results)}",
                    rule_section=f"Section 11 - {condition.value} Invalid Disputes",
                    rule_description=rule.description,
                    is_satisfied=is_invalid,
                    details=(
                        f"Dispute IS INVALID: {rule.description}"
                        if is_invalid
                        else f"Invalid rule does not apply: {rule.description}"
                    ),
                    applicable_region=rule.applicable_regions[0] if rule.applicable_regions else Region.ALL,
                )
            )

        return results

    def _evaluate_invalid_rule(self, task: DisputeTask, rule: InvalidDisputeRule) -> bool:
        """Evaluate whether an invalid dispute rule matches the task."""
        desc = rule.description.lower()
        txn = task.transaction

        if "mobile push payment" in desc:
            return False  # Would need explicit flag

        if "atm cash disbursement" in desc:
            return txn.environment == txn.environment.ATM

        if "straight through processing" in desc:
            return False  # Would need explicit flag

        if "chip-initiated transaction" in desc and "invalid" not in desc:
            return txn.is_chip_transaction and txn.has_full_chip_data

        if "visa secure" in desc and "authenticated" in desc:
            return txn.is_visa_secure

        if "cardholder states is fraudulent" in desc:
            return task.dispute_category == DisputeCategory.FRAUD and "fraudulent" in task.dispute_reason.lower()

        if "cardholder cancelled" in desc and "before" in desc and "expected delivery" in desc:
            return False  # Would need delivery date comparison

        if "quality" in desc and "merchandise" in desc:
            return "quality" in task.dispute_reason.lower()

        if "processed more than once" in desc:
            return "duplicate" in task.dispute_reason.lower()

        return False

    def check_time_limits(
        self, task: DisputeTask, condition: DisputeCondition
    ) -> TimeLimitResult | None:
        """Check if the dispute is within the applicable time limits."""
        category = self.get_category_for_condition(condition)
        rule_set = self.get_rule_set(category)
        time_limit_rules = rule_set.get_time_limits(condition)

        if not time_limit_rules or task.dispute_filing_date is None:
            return None

        # Find the most applicable time limit rule based on region
        applicable_rule = self._find_applicable_time_limit(time_limit_rules, task.region)
        if applicable_rule is None:
            return None

        # Determine start date
        start_date = self._get_time_limit_start_date(applicable_rule, task)
        deadline = applicable_rule.calculate_deadline(start_date)
        is_within = applicable_rule.is_within_limit(start_date, task.dispute_filing_date)
        days_remaining = (deadline - task.dispute_filing_date).days

        return TimeLimitResult(
            is_within_time_limit=is_within,
            time_limit_days=applicable_rule.calendar_days,
            start_date=start_date,
            deadline_date=deadline,
            days_remaining=max(0, days_remaining),
            rule_reference=f"Section 11 - {condition.value} Time Limit",
            notes=applicable_rule.notes,
        )

    def _find_applicable_time_limit(
        self, rules: list[TimeLimitRule], region: Region
    ) -> TimeLimitRule | None:
        """Find the most applicable time limit rule for a region."""
        # First try exact region match
        for rule in rules:
            if region in rule.applicable_regions:
                return rule
        # Fall back to ALL region
        for rule in rules:
            if Region.ALL in rule.applicable_regions:
                return rule
        return rules[0] if rules else None

    def _get_time_limit_start_date(self, rule: TimeLimitRule, task: DisputeTask) -> date:
        """Determine the start date for a time limit calculation."""
        if rule.start_from == "transaction_processing_date":
            return task.transaction.processing_date
        elif rule.start_from == "transaction_date":
            return task.transaction.transaction_date
        elif rule.start_from in (
            "transaction_date_of_adjustment",
            "original_credit_transaction_processing_date",
        ):
            return task.transaction.processing_date
        return task.transaction.processing_date

    def get_dispute_reasons(
        self, condition: DisputeCondition
    ) -> list[DisputeReasonRule]:
        """Get dispute reasons for a condition."""
        category = self.get_category_for_condition(condition)
        return self.get_rule_set(category).get_dispute_reasons(condition)

    def get_documentation_requirements(
        self, condition: DisputeCondition
    ) -> list[DocumentationRequirement]:
        """Get documentation requirements for a condition."""
        category = self.get_category_for_condition(condition)
        return self.get_rule_set(category).get_documentation_requirements(condition)

    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        """Get response requirements for a condition."""
        category = self.get_category_for_condition(condition)
        return self.get_rule_set(category).get_response_requirements(condition)

    def get_compelling_evidence_items(
        self, condition: DisputeCondition
    ) -> list[CompellingEvidenceItem]:
        """Get applicable compelling evidence items for a fraud dispute condition."""
        if self.get_category_for_condition(condition) != DisputeCategory.FRAUD:
            return []
        fraud_rules = self.get_rule_set(DisputeCategory.FRAUD)
        if isinstance(fraud_rules, FraudDisputeRules):
            all_items = fraud_rules.get_compelling_evidence_items()
            return [
                item for item in all_items
                if condition in item.applicable_conditions
            ]
        return []

    def evaluate_documentation_completeness(
        self, task: DisputeTask, condition: DisputeCondition
    ) -> RuleEvaluationResult:
        """Check if required documentation has been provided."""
        doc_requirements = self.get_documentation_requirements(condition)
        if not doc_requirements:
            return RuleEvaluationResult(
                rule_id=f"doc_check_{condition.value}",
                rule_section=f"Section 11 - {condition.value} Documentation",
                rule_description="Documentation completeness check",
                is_satisfied=True,
                details="No specific documentation requirements for this condition",
            )

        required_items: list[str] = []
        provided_items: list[str] = []
        for req in doc_requirements:
            required_items.extend(req.required_items)
            required_items.extend(req.certifications)

        # Check what evidence has been provided
        evidence_types = {e.evidence_type for e in task.evidence}
        evidence_descriptions = {e.description.lower() for e in task.evidence}

        for item in required_items:
            item_lower = item.lower()
            if any(
                item_lower in desc or desc in item_lower for desc in evidence_descriptions
            ) or any(item_lower in etype.lower() for etype in evidence_types):
                provided_items.append(item)

        # Check certifications
        if task.issuer_certification:
            provided_items.append("Issuer certification provided")
        if task.has_cardholder_letter:
            provided_items.append("Cardholder letter provided")

        is_complete = len(provided_items) >= len(required_items) or len(required_items) == 0
        missing = [item for item in required_items if item not in provided_items]

        return RuleEvaluationResult(
            rule_id=f"doc_check_{condition.value}",
            rule_section=f"Section 11 - {condition.value} Documentation",
            rule_description="Documentation completeness check",
            is_satisfied=is_complete,
            details=(
                "All required documentation provided"
                if is_complete
                else f"Missing documentation: {'; '.join(missing)}"
            ),
            evidence_required=required_items,
            evidence_provided=provided_items,
        )
