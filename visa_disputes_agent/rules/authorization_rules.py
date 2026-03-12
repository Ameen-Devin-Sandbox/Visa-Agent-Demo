"""Dispute Category 11: Authorization - Encoded rules from Visa Core Rules Section 11.8."""

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
    PreArbitrationRequirement,
    TimeLimitRule,
)


class AuthorizationDisputeRules(DisputeRuleSet):
    """Rules for Dispute Category 11: Authorization.

    Covers conditions 11.1-11.3 as defined in Visa Core Rules Section 11.8.
    """

    @property
    def category(self) -> DisputeCategory:
        return DisputeCategory.AUTHORIZATION

    @property
    def conditions(self) -> list[DisputeCondition]:
        return [
            DisputeCondition.CARD_RECOVERY_BULLETIN,
            DisputeCondition.DECLINED_AUTHORIZATION,
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT,
        ]

    def get_dispute_reasons(self, condition: DisputeCondition) -> list[DisputeReasonRule]:
        reasons: dict[DisputeCondition, list[DisputeReasonRule]] = {
            DisputeCondition.CARD_RECOVERY_BULLETIN: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Card Number was listed on the Card Recovery Bulletin before "
                        "the Transaction Date and the Merchant completed the Transaction "
                        "without obtaining Authorization."
                    ),
                    requirements=[
                        "card_on_recovery_bulletin",
                        "no_authorization_obtained",
                        "bulletin_date_before_transaction",
                    ],
                ),
            ],
            DisputeCondition.DECLINED_AUTHORIZATION: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Issuer or its agent sent a Decline Response to an Authorization "
                        "Request, but the Acquirer completed the Transaction anyway."
                    ),
                    requirements=[
                        "decline_response_sent",
                        "transaction_completed_after_decline",
                    ],
                ),
            ],
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "A valid Authorization was required but not obtained, or a valid "
                        "Authorization was obtained but the Transaction was not processed "
                        "within the required timeframe, or Authorization was not required "
                        "and the Transaction was not processed within the required timeframe."
                    ),
                    requirements=[
                        "authorization_missing_or_late_presentment",
                    ],
                ),
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Acquirer processed an Adjustment of an ATM Deposit Transaction "
                        "and either: posted to closed/credit problem account more than 10 days "
                        "after Transaction Date, or processed more than 45 days after "
                        "Transaction Date."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "atm_deposit_adjustment",
                        "late_adjustment_or_problem_account",
                    ],
                ),
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Acquirer processed an Adjustment of an ATM Cash Disbursement "
                        "and either: posted to closed/credit problem/fraud account more than "
                        "10 days after Transaction Date, or processed more than 45 days after "
                        "Transaction Date."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "atm_cash_disbursement_adjustment",
                        "late_adjustment_or_problem_account",
                    ],
                ),
            ],
        }
        return reasons.get(condition, [])

    def get_invalid_dispute_rules(self, condition: DisputeCondition) -> list[InvalidDisputeRule]:
        invalid_rules: dict[DisputeCondition, list[InvalidDisputeRule]] = {
            DisputeCondition.CARD_RECOVERY_BULLETIN: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
            ],
            DisputeCondition.DECLINED_AUTHORIZATION: [
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
                    description=(
                        "A Transaction for which Authorization was obtained after a Decline "
                        "Response was received for the same purchase (excludes Pickup "
                        "Response codes 04, 07, 41, 43)"
                    ),
                ),
            ],
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "Where a valid Authorization was required but not obtained for a "
                        "Credit Transaction with certain MCCs: 3000-3350 (Airlines), "
                        "4111 (Local Transit), 4112 (Railways), 4131 (Bus Lines), "
                        "4511 (Airlines NEC)"
                    ),
                ),
            ],
        }
        return invalid_rules.get(condition, [])

    def get_time_limits(self, condition: DisputeCondition) -> list[TimeLimitRule]:
        time_limits: dict[DisputeCondition, list[TimeLimitRule]] = {
            DisputeCondition.CARD_RECOVERY_BULLETIN: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.DECLINED_AUTHORIZATION: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=75,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=75,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
                TimeLimitRule(
                    condition=condition,
                    calendar_days=75,
                    start_from="transaction_date_of_adjustment",
                    applicable_regions=[Region.US],
                    notes=(
                        "For ATM Cash Disbursement or PIN-Authenticated Visa Debit "
                        "Transaction adjustment"
                    ),
                ),
            ],
        }
        return time_limits.get(condition, [])

    def get_documentation_requirements(
        self, condition: DisputeCondition
    ) -> list[DocumentationRequirement]:
        docs: dict[DisputeCondition, list[DocumentationRequirement]] = {
            DisputeCondition.DECLINED_AUTHORIZATION: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[],
                    certifications=[
                        (
                            "On the Dispute Processing Date, the Cardholder account status was "
                            "flagged as one of: Credit Problem, Closed, or Fraud"
                        ),
                    ],
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[],
                    certifications=[
                        (
                            "On the Dispute Processing Date, the Cardholder account status was "
                            "flagged as one of: Credit Problem, Closed, or Fraud"
                        ),
                    ],
                    applicable_regions=[Region.ALL],
                ),
            ],
        }
        return docs.get(condition, [])

    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        responses: dict[DisputeCondition, list[DisputeResponseRequirement]] = {
            DisputeCondition.DECLINED_AUTHORIZATION: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence of credit or Reversal not addressed by Issuer",
                        "Evidence that the Dispute is invalid",
                        "Evidence that Transaction was Chip-initiated and offline-authorized",
                        (
                            "For Car Rental/Cruise Line/Lodging: certification of check-in/out "
                            "dates, authorized amounts, and Authorization Codes"
                        ),
                    ],
                ),
            ],
            DisputeCondition.NO_AUTHORIZATION_LATE_PRESENTMENT: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence of credit or Reversal not addressed by Issuer",
                        "Evidence that the Dispute is invalid",
                        (
                            "Transaction Receipt with correct Transaction Date proving "
                            "timely presentment and valid authorization"
                        ),
                        (
                            "For special Authorization procedures: evidence of Estimated "
                            "and Incremental Authorization Requests with same Transaction "
                            "Identifier"
                        ),
                    ],
                ),
            ],
        }
        return responses.get(condition, [])

    def get_pre_arbitration_requirements(
        self, condition: DisputeCondition
    ) -> list[PreArbitrationRequirement]:
        """Get pre-arbitration requirements for authorization disputes."""
        pre_arb: dict[DisputeCondition, list[PreArbitrationRequirement]] = {
            DisputeCondition.DECLINED_AUTHORIZATION: [
                PreArbitrationRequirement(
                    condition=condition,
                    required_documentation=[
                        "Evidence of credit or Reversal not addressed by Issuer",
                        "Evidence that the Dispute is invalid",
                        "Evidence that Transaction was Chip-initiated and offline-authorized",
                    ],
                ),
            ],
        }
        return pre_arb.get(condition, [])
