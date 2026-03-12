"""Dispute Category 13: Consumer Disputes - Encoded rules from Visa Core Rules Section 11.10."""

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


class ConsumerDisputeRules(DisputeRuleSet):
    """Rules for Dispute Category 13: Consumer Disputes.

    Covers conditions 13.1-13.9 as defined in Visa Core Rules Section 11.10.
    """

    @property
    def category(self) -> DisputeCategory:
        return DisputeCategory.CONSUMER_DISPUTES

    @property
    def conditions(self) -> list[DisputeCondition]:
        return [
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED,
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED,
            DisputeCondition.COUNTERFEIT_MERCHANDISE,
            DisputeCondition.MISREPRESENTATION,
            DisputeCondition.DEFECTIVE_MERCHANDISE,
            DisputeCondition.CANCELLED_RECURRING,
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES,
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED,
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM,
        ]

    def get_dispute_reasons(self, condition: DisputeCondition) -> list[DisputeReasonRule]:
        reasons: dict[DisputeCondition, list[DisputeReasonRule]] = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder did not receive the merchandise or services, or "
                        "received only partial merchandise or services. The Cardholder "
                        "must have attempted to resolve with the Merchant first."
                    ),
                    requirements=[
                        "merchandise_or_services_not_received",
                        "cardholder_attempted_merchant_resolution",
                        "cardholder_financial_loss",
                    ],
                ),
            ],
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The merchandise or services received differ materially from what "
                        "was described by the Merchant at the time of the Transaction, "
                        "or the merchandise received was damaged or defective."
                    ),
                    requirements=[
                        "merchandise_materially_different",
                        "cardholder_attempted_merchant_resolution",
                        "cardholder_attempted_return_if_applicable",
                    ],
                ),
            ],
            DisputeCondition.COUNTERFEIT_MERCHANDISE: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The merchandise received by the Cardholder is counterfeit. "
                        "The Cardholder must have a determination from the rights holder, "
                        "or an expert, that the merchandise is counterfeit."
                    ),
                    requirements=[
                        "counterfeit_determination",
                        "cardholder_attempted_merchant_resolution",
                    ],
                ),
            ],
            DisputeCondition.MISREPRESENTATION: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Merchant misrepresented the merchandise or services at the "
                        "time of the Transaction. The actual terms or conditions were "
                        "different from what was disclosed."
                    ),
                    requirements=[
                        "merchant_misrepresentation",
                        "cardholder_attempted_merchant_resolution",
                    ],
                ),
            ],
            DisputeCondition.DEFECTIVE_MERCHANDISE: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The merchandise received was defective and the Cardholder returned "
                        "or attempted to return it to the Merchant."
                    ),
                    requirements=[
                        "merchandise_defective",
                        "cardholder_returned_or_attempted_return",
                        "cardholder_attempted_merchant_resolution",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_RECURRING: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder withdrew permission to charge the account for "
                        "a Recurring Transaction or notified the Merchant to cancel, "
                        "but the Merchant continued to process Recurring Transactions."
                    ),
                    requirements=[
                        "recurring_transaction",
                        "cardholder_cancelled_recurring",
                        "merchant_continued_charging",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder cancelled or returned merchandise or services, "
                        "or the Merchant cancelled the Transaction, but a credit or "
                        "Reversal was not processed."
                    ),
                    requirements=[
                        "cancellation_or_return_occurred",
                        "no_credit_processed",
                    ],
                ),
            ],
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "An Original Credit Transaction was not accepted because the "
                        "recipient refused it, or OCTs are prohibited by applicable "
                        "laws or regulations."
                    ),
                    requirements=[
                        "original_credit_transaction",
                        "recipient_refused_or_prohibited",
                    ],
                ),
            ],
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder participated in the Transaction and did not receive "
                        "cash or received a partial amount from an ATM."
                    ),
                    requirements=[
                        "atm_transaction",
                        "cash_not_received_or_partial",
                        "cardholder_participated",
                    ],
                ),
            ],
        }
        return reasons.get(condition, [])

    def get_invalid_dispute_rules(self, condition: DisputeCondition) -> list[InvalidDisputeRule]:
        invalid_rules: dict[DisputeCondition, list[InvalidDisputeRule]] = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: [
                InvalidDisputeRule(
                    condition=condition,
                    description="An ATM Cash Disbursement",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Straight Through Processing Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction in which the Cardholder cancelled before the "
                        "expected delivery date"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction in which merchandise is held by Cardholder's "
                        "country's customs agency"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Transaction that the Cardholder states is fraudulent",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Dispute regarding the quality of merchandise or service",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A partial Advance Payment when the remaining balance was not "
                        "paid and Merchant is willing to provide merchandise/services"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="The Cash-Back portion of a Visa Cash-Back Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="An Automated Fuel Dispenser Transaction",
                ),
            ],
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: [
                InvalidDisputeRule(
                    condition=condition,
                    description="An ATM Cash Disbursement",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Transaction that the Cardholder states is fraudulent",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Dispute about merchandise quality when it was described "
                        "accurately by the Merchant"
                    ),
                ),
            ],
            DisputeCondition.CANCELLED_RECURRING: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction that the Cardholder states is fraudulent "
                        "(use Dispute Category 10 instead)"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Debt Repayment Transaction",
                ),
            ],
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: [
                InvalidDisputeRule(
                    condition=condition,
                    description="An ATM Cash Disbursement",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Transaction that the Cardholder states is fraudulent",
                ),
            ],
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
            ],
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Cash-In Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Cash-Out Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Transaction that the Cardholder states is fraudulent",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Transaction that was processed more than once",
                ),
            ],
        }
        return invalid_rules.get(condition, [])

    def get_time_limits(self, condition: DisputeCondition) -> list[TimeLimitRule]:
        time_limits: dict[DisputeCondition, list[TimeLimitRule]] = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                    waiting_period_days=15,
                    waiting_period_description=(
                        "Wait 15 calendar days from Transaction Date or expected delivery date"
                    ),
                    max_calendar_days=540,
                    notes=(
                        "Can also be 120 days from last date Cardholder expected to receive "
                        "merchandise/services, not to exceed 540 days from processing date"
                    ),
                ),
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.EUROPE],
                    waiting_period_days=15,
                    waiting_period_description=(
                        "Wait 15 calendar days. For MCC 4722 (Travel Agencies), wait 30 days. "
                        "For bonding authority claims, wait 60 days."
                    ),
                    max_calendar_days=540,
                ),
            ],
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                    max_calendar_days=540,
                    notes=(
                        "120 days from Transaction Processing Date or from date Cardholder "
                        "returned/attempted to return merchandise"
                    ),
                ),
            ],
            DisputeCondition.COUNTERFEIT_MERCHANDISE: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                    max_calendar_days=540,
                ),
            ],
            DisputeCondition.CANCELLED_RECURRING: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                    max_calendar_days=540,
                    notes=(
                        "120 days from Transaction Processing Date or from date Merchant "
                        "agreed to credit (whichever is later)"
                    ),
                ),
            ],
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="original_credit_transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
        }
        return time_limits.get(condition, [])

    def get_documentation_requirements(
        self, condition: DisputeCondition
    ) -> list[DocumentationRequirement]:
        docs: dict[DisputeCondition, list[DocumentationRequirement]] = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Detailed description of merchandise or services purchased",
                    ],
                    certifications=[
                        "Services not rendered by expected date/time",
                        "Merchandise not received by expected date/time",
                        "Cardholder attempted to resolve with Merchant",
                    ],
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Detailed description of merchandise/services as described by Merchant",
                        "Detailed description of merchandise/services actually received",
                        "Explanation of how they materially differ",
                    ],
                    certifications=[
                        "Cardholder attempted to resolve with Merchant",
                        "Cardholder returned or attempted to return merchandise (if applicable)",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_RECURRING: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Evidence of cancellation notification to Merchant",
                        "Date of cancellation",
                    ],
                    certifications=[
                        "Cardholder cancelled or withdrew permission for recurring charges",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Evidence of cancellation or return",
                        "Detailed description of merchandise or services",
                    ],
                    certifications=[
                        "Merchandise was returned or cancellation was communicated",
                        "Credit or Reversal was not processed by Merchant",
                    ],
                ),
            ],
            DisputeCondition.ORIGINAL_CREDIT_TRANSACTION_NOT_ACCEPTED: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[],
                    certifications=[
                        "OCT not allowed by applicable laws/regulations",
                        "Recipient refused to accept the OCT",
                    ],
                ),
            ],
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[],
                    certifications=[
                        "Cardholder did not receive cash",
                        "Amount Cardholder received (if partial)",
                    ],
                ),
            ],
        }
        return docs.get(condition, [])

    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        common_evidence = [
            "Evidence of credit or Reversal not addressed by Issuer",
            "Evidence that the Dispute is invalid",
            "Evidence that the Cardholder no longer disputes the Transaction",
        ]

        responses: dict[DisputeCondition, list[DisputeResponseRequirement]] = {
            DisputeCondition.MERCHANDISE_SERVICES_NOT_RECEIVED: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        *common_evidence,
                        "Evidence that merchandise/services were provided",
                        "Proof of delivery (signature not required if AVS match)",
                    ],
                ),
            ],
            DisputeCondition.MERCHANDISE_NOT_AS_DESCRIBED: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        *common_evidence,
                        "Evidence that merchandise/services matched description",
                        "Evidence that Cardholder did not attempt to return merchandise",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_RECURRING: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        *common_evidence,
                        "Evidence that cancellation was not received",
                        "Evidence of signed agreement for recurring charges",
                        "Evidence that Cardholder was informed of cancellation procedures",
                    ],
                ),
            ],
            DisputeCondition.CANCELLED_MERCHANDISE_SERVICES: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        *common_evidence,
                        (
                            "Transaction Receipt proving Merchant disclosed limited return "
                            "or cancellation policy at time of Transaction"
                        ),
                    ],
                ),
            ],
            DisputeCondition.NON_RECEIPT_OF_CASH_ATM: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        *common_evidence,
                        (
                            "Copy of ATM Cash Disbursement Transaction with Payment Credential, "
                            "transaction time, and indicator confirming successful disbursement"
                        ),
                    ],
                ),
            ],
        }
        return responses.get(condition, [
            DisputeResponseRequirement(
                condition=condition,
                required_evidence=common_evidence,
            ),
        ])
