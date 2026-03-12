"""Dispute Category 10: Fraud - Encoded rules from Visa Core Rules Section 11.7."""

from __future__ import annotations

from visa_disputes_agent.models.enums import (
    DisputeCategory,
    DisputeCondition,
    Region,
    TransactionEnvironment,
)
from visa_disputes_agent.rules.base import (
    CompellingEvidenceItem,
    DisputeReasonRule,
    DisputeResponseRequirement,
    DisputeRuleSet,
    DocumentationRequirement,
    InvalidDisputeRule,
    PreArbitrationRequirement,
    TimeLimitRule,
)


class FraudDisputeRules(DisputeRuleSet):
    """Rules for Dispute Category 10: Fraud.

    Covers conditions 10.1-10.5 as defined in Visa Core Rules Section 11.7.
    """

    @property
    def category(self) -> DisputeCategory:
        return DisputeCategory.FRAUD

    @property
    def conditions(self) -> list[DisputeCondition]:
        return [
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT,
            DisputeCondition.EMV_LIABILITY_SHIFT_NON_COUNTERFEIT,
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
            DisputeCondition.VISA_FRAUD_MONITORING_PROGRAM,
        ]

    def get_dispute_reasons(self, condition: DisputeCondition) -> list[DisputeReasonRule]:
        reasons: dict[DisputeCondition, list[DisputeReasonRule]] = {
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "Transaction qualifies for EMV liability shift, was completed with a "
                        "Counterfeit Card in Card-Present Environment, Cardholder denies "
                        "authorization, Card is a Chip Card, and one of: (1) Transaction did not "
                        "take place at Chip-Reading Device, (2) Transaction was Chip-initiated "
                        "and Acquirer did not transmit Full-Chip Data in Authorization Request, "
                        "(3) Transaction was approved offline and Acquirer did not transmit "
                        "Full-Chip Data in Clearing Record."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "emv_liability_shift_qualifies",
                        "counterfeit_card",
                        "card_present_environment",
                        "cardholder_denies_authorization",
                        "card_is_chip_card",
                        "chip_reading_device_or_data_issue",
                    ],
                ),
            ],
            DisputeCondition.EMV_LIABILITY_SHIFT_NON_COUNTERFEIT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "Transaction qualifies for EMV liability shift for non-counterfeit "
                        "fraud (lost, stolen, or not received item). Cardholder denies "
                        "authorization or participation in the transaction."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "emv_liability_shift_qualifies",
                        "non_counterfeit_fraud",
                        "cardholder_denies_authorization",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder participated in the Transaction but denies "
                        "authorization. The Card was present at the point of Transaction."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "card_present_environment",
                        "cardholder_denies_authorization",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "The Cardholder denies authorization of or participation in a "
                        "Card-Absent Environment Transaction. Includes e-commerce, "
                        "mail/telephone order, and recurring transactions."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "card_absent_environment",
                        "cardholder_denies_authorization",
                    ],
                ),
            ],
            DisputeCondition.VISA_FRAUD_MONITORING_PROGRAM: [
                DisputeReasonRule(
                    condition=condition,
                    description=(
                        "Transaction involves a Merchant identified through the Visa Fraud "
                        "Monitoring Program (VFMP) or the Visa Acquirer Monitoring Program "
                        "(VAMP)."
                    ),
                    applicable_regions=[Region.ALL],
                    requirements=[
                        "merchant_in_monitoring_program",
                        "cardholder_denies_authorization",
                    ],
                ),
            ],
        }
        return reasons.get(condition, [])

    def get_invalid_dispute_rules(self, condition: DisputeCondition) -> list[InvalidDisputeRule]:
        invalid_rules: dict[DisputeCondition, list[InvalidDisputeRule]] = {
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Chip-initiated Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="An Emergency Cash Disbursement",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Fallback Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction for which the Authorization record contains POS Entry "
                        "Mode code 90 and the Service Code encoded on the Magnetic Stripe does "
                        "not indicate the presence of a Chip"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction for which the Authorization Request contains the CVV but "
                        "CVV verification was not performed or the CVV was verified successfully"
                    ),
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Transaction that qualifies under Dispute Condition 10.1 "
                        "(EMV Liability Shift Counterfeit Fraud)"
                    ),
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                InvalidDisputeRule(
                    condition=condition,
                    description="A Mobile Push Payment Transaction",
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description=(
                        "A Visa Secure-authenticated Transaction where authentication "
                        "was performed by the Issuer (liability shift applies)"
                    ),
                ),
                InvalidDisputeRule(
                    condition=condition,
                    description="A Straight Through Processing Transaction",
                ),
            ],
        }
        return invalid_rules.get(condition, [])

    def get_time_limits(self, condition: DisputeCondition) -> list[TimeLimitRule]:
        time_limits: dict[DisputeCondition, list[TimeLimitRule]] = {
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                    notes="Must report fraud to Visa using fraud type code 4 before initiating",
                ),
            ],
            DisputeCondition.EMV_LIABILITY_SHIFT_NON_COUNTERFEIT: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                TimeLimitRule(
                    condition=condition,
                    calendar_days=120,
                    start_from="transaction_processing_date",
                    applicable_regions=[Region.ALL],
                ),
            ],
            DisputeCondition.VISA_FRAUD_MONITORING_PROGRAM: [
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
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Fraud report to Visa using fraud type code 4 (counterfeit)",
                    ],
                    certifications=[
                        "Issuer certifies cardholder denies authorization or participation",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_PRESENT: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Cardholder letter denying authorization or Issuer certification",
                    ],
                    certifications=[
                        "Cardholder's complete or partial Payment Credential",
                        "Merchant name(s)",
                        "Transaction amount(s)",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                DocumentationRequirement(
                    condition=condition,
                    required_items=[
                        "Cardholder letter denying authorization or Issuer certification",
                    ],
                    certifications=[
                        "Cardholder's complete or partial Payment Credential",
                        "Merchant name(s)",
                        "Transaction amount(s)",
                    ],
                ),
            ],
        }
        return docs.get(condition, [])

    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        responses: dict[DisputeCondition, list[DisputeResponseRequirement]] = {
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence that a credit or Reversal was issued and not addressed",
                        "Evidence that the Dispute is invalid",
                        "Evidence that the Cardholder no longer disputes the Transaction",
                        "Compelling evidence as specified in Section 11.5.2",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                DisputeResponseRequirement(
                    condition=condition,
                    required_evidence=[
                        "Evidence that a credit or Reversal was issued and not addressed",
                        "Evidence that the Dispute is invalid",
                        "Evidence that the Cardholder no longer disputes the Transaction",
                        "Compelling evidence as specified in Section 11.5.2",
                        "Evidence of Visa Secure authentication performed by Issuer",
                    ],
                ),
            ],
        }
        return responses.get(condition, [])

    def get_pre_arbitration_requirements(
        self, condition: DisputeCondition
    ) -> list[PreArbitrationRequirement]:
        """Get pre-arbitration requirements for fraud disputes."""
        pre_arb: dict[DisputeCondition, list[PreArbitrationRequirement]] = {
            DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT: [
                PreArbitrationRequirement(
                    condition=condition,
                    required_documentation=[
                        "Compelling evidence as specified in the allowable evidence table",
                    ],
                ),
            ],
            DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
                PreArbitrationRequirement(
                    condition=condition,
                    required_documentation=[
                        "Compelling evidence linking cardholder to transaction",
                        "Evidence of 3+ matching data points from undisputed transactions",
                    ],
                ),
            ],
        }
        return pre_arb.get(condition, [])

    def get_compelling_evidence_items(self) -> list[CompellingEvidenceItem]:
        """Get the compelling evidence table for fraud disputes (Table 11-6)."""
        return [
            CompellingEvidenceItem(
                item_number=1,
                description=(
                    "Photographic or email evidence proving link between person receiving "
                    "merchandise/services and Cardholder, or proving Cardholder possesses "
                    "the merchandise"
                ),
                applicable_conditions=[
                    DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT,
                    DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
                    DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
                ],
            ),
            CompellingEvidenceItem(
                item_number=2,
                description=(
                    "For Card-Absent Transaction with merchandise collected from Merchant: "
                    "Cardholder signature on pick-up form, copy of identification, or "
                    "details of identification"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                applicable_environments=[TransactionEnvironment.CARD_ABSENT],
            ),
            CompellingEvidenceItem(
                item_number=3,
                description=(
                    "For Card-Absent Transaction with delivered merchandise: evidence item "
                    "was delivered to same physical address with AVS match of Y or M"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                applicable_environments=[TransactionEnvironment.CARD_ABSENT],
            ),
            CompellingEvidenceItem(
                item_number=4,
                description=(
                    "For e-commerce digital goods: description of downloaded merchandise, "
                    "date/time of download, and 2+ of: IP address/location, device ID, "
                    "email linked to profile, verified profile, post-transaction access, "
                    "same device/card used in undisputed transaction"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                applicable_environments=[TransactionEnvironment.ECOMMERCE],
                min_sub_requirements=2,
                sub_requirements=[
                    "Purchaser's IP address and device geographical location",
                    "Device ID number and name of device",
                    "Purchaser's name and email linked to customer profile",
                    "Verified merchant profile accessed before Transaction Date",
                    "Evidence website/app accessed on or after Transaction Date",
                    "Same device and Card used in undisputed transaction",
                ],
            ),
            CompellingEvidenceItem(
                item_number=10,
                description=(
                    "For Card-Absent Transaction: evidence that 3+ of the following matched "
                    "an undisputed transaction or OCT: customer account/login ID, delivery "
                    "address, device ID/fingerprint, email, IP address, telephone number"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                applicable_environments=[TransactionEnvironment.CARD_ABSENT],
                min_sub_requirements=3,
                sub_requirements=[
                    "Customer account/login ID",
                    "Delivery address",
                    "Device ID/device fingerprint",
                    "Email address",
                    "IP address",
                    "Telephone number",
                ],
            ),
            CompellingEvidenceItem(
                item_number=11,
                description=(
                    "Evidence that the Transaction was completed by a member of the "
                    "Cardholder's household or family"
                ),
                applicable_conditions=[
                    DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT,
                    DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
                    DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
                ],
            ),
            CompellingEvidenceItem(
                item_number=12,
                description="Evidence of one or more non-disputed payments for same merchandise/service",
                applicable_conditions=[
                    DisputeCondition.EMV_LIABILITY_SHIFT_COUNTERFEIT,
                    DisputeCondition.OTHER_FRAUD_CARD_PRESENT,
                    DisputeCondition.OTHER_FRAUD_CARD_ABSENT,
                ],
            ),
            CompellingEvidenceItem(
                item_number=13,
                description=(
                    "For Recurring Transaction: legally binding contract, evidence cardholder "
                    "is using merchandise/services, and previous undisputed transaction"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                applicable_environments=[TransactionEnvironment.RECURRING],
                sub_requirements=[
                    "Legally binding contract between Merchant and Cardholder",
                    "Cardholder is using the merchandise or services",
                    "Previous transaction that was not disputed",
                ],
            ),
            CompellingEvidenceItem(
                item_number=16,
                description=(
                    "For cryptocurrency/NFT transactions: destination wallet address, "
                    "blockchain transaction hash (searchable on open-source website), "
                    "or prior approved similar transactions"
                ),
                applicable_conditions=[DisputeCondition.OTHER_FRAUD_CARD_ABSENT],
                sub_requirements=[
                    "Destination wallet address",
                    "Blockchain transaction hash (searchable/traceable)",
                    "Prior approved similar Transactions using same Payment Credential",
                ],
            ),
        ]
