"""Dispute Category 12: Processing Errors - Encoded rules from Visa Core Rules Section 11.9."""

from __future__ import annotations

from visa_disputes_agent.models.enums import (
    DisputeCategory,
    DisputeCondition,
    Region,
)
from visa_disputes_agent.rules.base import (
    DisputeReasonRule,
    DisputeResponseRequirement,
    DisputeRuleSet,
    DocumentationRequirement,
    InvalidDisputeRule,
    TimeLimitRule,
)


class ProcessingErrorDisputeRules(DisputeRuleSet):
    """Rules for Dispute Category 12: Processing Errors.

    Covers conditions 12.1-12.9 as defined in Visa Core Rules Section 11.9.
    """

    @property
    def category(self) -> DisputeCategory:
        return DisputeCategory.PROCESSING_ERRORS

    @property
    def conditions(self) -> list[DisputeCondition]:
        return [
            DisputeCondition.INCORRECT_TRANSACTION_CODE,
            DisputeCondition.INCORRECT_AMOUNT,
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER,
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER_CROSS_BORDER,
            DisputeCondition.DUPLICATE_PROCESSING,
            DisputeCondition.PAID_BY_OTHER_MEANS,
            DisputeCondition.INVALID_DATA,
            DisputeCondition.LATE_PRESENTMENT,
            DisputeCondition.INCORRECT_CURRENCY,
        ]

    def get_dispute_reasons(self, condition: DisputeCondition) -> list[DisputeReasonRule]:
        reasons: dict[DisputeCondition, list[DisputeReasonRule]] = {
            DisputeCondition.INCORRECT_TRANSACTION_CODE: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Transaction was processed with an incorrect Transaction code. "
                        "For example, a Credit Transaction was processed as a Debit, or a "
                        "Debit was processed as a Credit."
                    ),
                    requirements=["incorrect_transaction_code"],
                ),
            ],
            DisputeCondition.INCORRECT_AMOUNT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Transaction amount differs from the amount the Cardholder agreed "
                        "to pay or the amount on the Transaction Receipt."
                    ),
                    requirements=[
                        "amount_differs_from_agreed",
                        "cardholder_confirms_correct_amount",
                    ],
                ),
            ],
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Transaction was posted to the wrong account. The Issuer's "
                        "Cardholder was not involved in the Transaction."
                    ),
                    requirements=[
                        "transaction_posted_to_wrong_account",
                        "cardholder_not_involved",
                    ],
                ),
            ],
            DisputeCondition.DUPLICATE_PROCESSING: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "A single Transaction was processed more than once to the "
                        "Cardholder's account."
                    ),
                    requirements=["duplicate_transaction_processed"],
                ),
            ],
            DisputeCondition.PAID_BY_OTHER_MEANS: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder or Issuer has proof that the Transaction was paid "
                        "by other means (cash, check, or other credit/debit card)."
                    ),
                    requirements=["paid_by_other_means_evidence"],
                ),
            ],
            DisputeCondition.LATE_PRESENTMENT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Transaction was not processed within the required timeframe. "
                        "The Clearing Record was submitted late."
                    ),
                    requirements=["late_clearing_submission"],
                ),
            ],
            DisputeCondition.INCORRECT_CURRENCY: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Transaction was processed in an incorrect currency or the "
                        "currency conversion was incorrect."
                    ),
                    requirements=["incorrect_currency_processing"],
                ),
            ],
        }
        return reasons.get(condition, [])

    def get_invalid_dispute_rules(self, condition: DisputeCondition) -> list[InvalidDisputeRule]:
        invalid_rules: dict[DisputeCondition, list[InvalidDisputeRule]] = {
            DisputeCondition.INCORRECT_TRANSACTION_CODE: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
            ],
            DisputeCondition.INCORRECT_AMOUNT: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction where the difference is solely due to currency "
                        "conversion (use Dispute Condition 12.9 instead)"
                    ),
                ),
            ],
            DisputeCondition.DUPLICATE_PROCESSING: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "Multiple Clearing Sequence Numbers from the same Authorization "
                        "(split shipments)"
                    ),
                ),
            ],
            DisputeCondition.PAID_BY_OTHER_MEANS: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="An ATM Cash Disbursement",
                ),
            ],
        }
        return invalid_rules.get(condition, [])

    def get_time_limits(self, condition: DisputeCondition) -> list[TimeLimitRule]:
        # Most processing error disputes have 120-day time limits
        default_limit = TimeLimitRule(
            condition=condition,
            calendar_days=120,
            start_from="transaction_processing_date",
            applicable_regions=[Region.ALL],
        )

        time_limits: dict[DisputeCondition, list[TimeLimitRule]] = {
            DisputeCondition.INCORRECT_TRANSACTION_CODE: [default_limit],
            DisputeCondition.INCORRECT_AMOUNT: [default_limit],
            DisputeCondition.INCORRECT_ACCOUNT_NUMBER: [default_limit],
            DisputeCondition.DUPLICATE_PROCESSING: [default_limit],
            DisputeCondition.PAID_BY_OTHER_MEANS: [default_limit],
            DisputeCondition.LATE_PRESENTMENT: [default_limit],
            DisputeCondition.INCORRECT_CURRENCY: [default_limit],
        }
        return time_limits.get(condition, [default_limit])

    def get_documentation_requirements(
        self, condition: DisputeCondition
    ) -> list[DocumentationRequirement]:
        docs: dict[DisputeCondition, list[DocumentationRequirement]] = {
            DisputeCondition.INCORRECT_AMOUNT: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Transaction Receipt or other documentation showing correct amount",
                    ],
                    certifications=[
                        "Certification of the correct Transaction amount",
                    ],
                ),
            ],
            DisputeCondition.DUPLICATE_PROCESSING: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Documentation of both the original and duplicate transactions",
                    ],
                    certifications=[
                        "Certification that only one Transaction occurred",
                        "Transaction Identifiers for both the original and duplicate",
                    ],
                ),
            ],
            DisputeCondition.PAID_BY_OTHER_MEANS: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Proof of payment by other means (receipt, bank statement, etc.)",
                    ],
                    certifications=[
                        "Certification of the other means of payment used",
                    ],
                ),
            ],
        }
        return docs.get(condition, [])

    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        # Common response structure for most processing error disputes
        common_response = DisputeResponseRequirement(
            condition=condition,
            required_evidence=[
                "Evidence of credit or Reversal not addressed by Issuer",
                "Evidence that the Dispute is invalid",
                "Evidence that the Cardholder no longer disputes the Transaction",
            ],
        )

        responses: dict[DisputeCondition, list[DisputeResponseRequirement]] = {
            DisputeCondition.INCORRECT_AMOUNT: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence of credit or Reversal not addressed by Issuer",
                        "Evidence that the Dispute is invalid",
                        "Correct Transaction Receipt showing agreed amount",
                    ],
                ),
            ],
            DisputeCondition.DUPLICATE_PROCESSING: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence of credit or Reversal not addressed by Issuer",
                        "Evidence that the Dispute is invalid",
                        "Evidence that each Transaction is a separate valid Transaction",
                        "Documentation proving transactions are distinct purchases",
                    ],
                ),
            ],
        }
        return responses.get(condition, [common_response])
