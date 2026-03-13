"""Category 13: Consumer Disputes — Dispute condition rules (13.1 through 13.9).

Encoded from Visa Core Rules Chapter 11, Section 11.10.
"""

from __future__ import annotations

from src.models.enums import DisputeCondition, TransactionEnvironment
from src.rules.models import (
    DisputeConditionRule,
    DocumentRequirement,
    InvalidCondition,
    PreArbitrationRight,
    TimeLimitRule,
)

CONSUMER_CONDITIONS: list[DisputeConditionRule] = [
    # ── 13.1: Merchandise/Services Not Received ──────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_NOT_RECEIVED,
        name="Merchandise/Services Not Received",
        description="Cardholder participated but did not receive merchandise/services.",
        rule_section="11.10.2",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE],
        triggers=[
            "Cardholder participated but didn't receive merchandise/services",
            "Merchant unwilling or unable to provide",
        ],
        prerequisites=[
            "Cardholder must attempt to resolve with Merchant/liquidator first",
            "If late delivery, must return or attempt to return merchandise",
            "Merchant responsible for customs in Merchant's country",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            wait_days_before=15,
            max_calendar_days=540,
            description="Wait 15 cal days from txn/return/cancellation (30 for MCC 4722 Travel Agencies). Then 120 cal days from Processing Date or last expected receipt date. Max 540 cal days.",
        ),
        dispute_amount_rule="Limited to portion of merchandise/services not received",
        invalid_conditions=[
            InvalidCondition("13.1-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("13.1-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.1-INV-03", "Cardholder cancelled before expected delivery date"),
            InvalidCondition("13.1-INV-04", "Merchandise held in cardholder's customs (non-Merchant country)"),
            InvalidCondition("13.1-INV-05", "Cardholder states transaction is fraudulent"),
            InvalidCondition("13.1-INV-06", "Quality dispute (not as described)"),
            InvalidCondition("13.1-INV-07", "Partial advance payment when Merchant still willing to provide"),
            InvalidCondition("13.1-INV-08", "Cash-back portion of transaction"),
            InvalidCondition("13.1-INV-09", "AFD transaction"),
            InvalidCondition("13.1-INV-10", "Crypto: access issues post-delivery to wallet"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.1-DOC-01", "Certification of non-receipt", "non_receipt_certification"),
            DocumentRequirement("13.1-DOC-02", "Detailed description of merchandise/services", "merchandise_description"),
            DocumentRequirement("13.1-DOC-03", "Cardholder letter if 3+ disputes at same merchant in 30 days", "cardholder_letter", is_mandatory=False),
            DocumentRequirement("13.1-DOC-04", "Europe: bonding authority information", "bonding_authority_info", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration (after Dispute Response)",
                actor="issuer",
                evidence_types=[
                    "New documentation/information",
                    "Changed dispute condition",
                    "Certification cardholder still disputes",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence of delivery",
            "Airline flight departure evidence",
            "Crypto: wallet delivery proof (blockchain hash, wallet address)",
        ],
    ),
    # ── 13.2: Cancelled Recurring Transaction ────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_CANCELLED_RECURRING,
        name="Cancelled Recurring Transaction",
        description="Cardholder withdrew permission for Recurring or Installment (Europe) transaction.",
        rule_section="11.10.3",
        environments=[TransactionEnvironment.RECURRING, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Cardholder withdrew permission for Recurring Transaction",
            "OR: Cardholder withdrew permission for Installment (Europe only)",
            "OR: Acquirer/Merchant notified account closed before processing",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Limited to unused portion of service/merchandise",
        invalid_conditions=[
            InvalidCondition("13.2-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("13.2-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.2-INV-03", "Installment Transaction (excluding Europe)"),
            InvalidCondition("13.2-INV-04", "Unscheduled Credential-on-File transaction"),
            InvalidCondition("13.2-INV-05", "Transaction cardholder states is fraudulent"),
            InvalidCondition("13.2-INV-06", "Cardholder-initiated Transaction"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.2-DOC-01", "Certification: withdrawal date, contact details used, other payment info", "cancellation_certification"),
            DocumentRequirement("13.2-DOC-02", "OR: account closure notification date", "account_closure_notification", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration (after Dispute Response)",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                    "Certification cardholder still disputes",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence: different cancellation date + services provided after",
            "Merchant posted after service was rendered",
            "Cardholder used services after withdrawal date",
        ],
    ),
    # ── 13.3: Not as Described or Defective ──────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_NOT_AS_DESCRIBED,
        name="Not as Described or Defective Merchandise/Services",
        description="Merchandise didn't match description, was damaged/defective, or quality dispute.",
        rule_section="11.10.4",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE],
        triggers=[
            "Merchandise didn't match Transaction Receipt/description",
            "Merchandise damaged or defective",
            "Quality dispute",
            "Contractual agreement not honored (Visa Commercial Virtual Account)",
            "Crypto/NFT not as described",
        ],
        prerequisites=[
            "Cardholder must attempt to resolve with Merchant",
            "Cardholder must return or attempt to return merchandise",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            wait_days_before=15,
            max_calendar_days=540,
            description="Wait 15 cal days. Then 120 days from Processing Date or receipt date. OR 60 days from first notification if ongoing negotiations within 120 days. Max 540 days.",
        ),
        dispute_amount_rule="Limited to unused portion or returned value",
        invalid_conditions=[
            InvalidCondition("13.3-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("13.3-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.3-INV-03", "VAT"),
            InvalidCondition("13.3-INV-04", "Customs charges (non-Merchant country)"),
            InvalidCondition("13.3-INV-05", "Cash-back portion"),
            InvalidCondition("13.3-INV-06", "Cardholder states transaction is fraudulent"),
            InvalidCondition("13.3-INV-07", "AFD transaction"),
            InvalidCondition("13.3-INV-08", "Quality of food from restaurants"),
            InvalidCondition("13.3-INV-09", "Crypto: value decrease only"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.3-DOC-01", "Explanation of issue", "issue_explanation"),
            DocumentRequirement("13.3-DOC-02", "Dates received and returned", "receipt_return_dates"),
            DocumentRequirement("13.3-DOC-03", "Shipping information", "shipping_info", is_mandatory=False),
            DocumentRequirement("13.3-DOC-04", "For attempted return: certification Merchant refused/no RMA/instructed not to return", "return_attempt_certification", is_mandatory=False),
            DocumentRequirement("13.3-DOC-05", "For ongoing negotiations: dates + evidence", "negotiation_evidence", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration (after Dispute Response)",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                    "Certification cardholder still disputes",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence merchandise matched description",
            "Evidence of agreed-upon terms",
        ],
    ),
    # ── 13.4: Counterfeit Merchandise ────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_COUNTERFEIT_MERCH,
        name="Counterfeit Merchandise",
        description="Merchandise identified as counterfeit by qualified authority.",
        rule_section="11.10.5",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE],
        triggers=[
            "Merchandise identified as counterfeit by IP owner/representative",
            "OR: Identified by customs/law enforcement",
            "OR: Identified by third-party expert",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            max_calendar_days=540,
            description="120 calendar days from Processing Date, receipt date, or notification date. Max 540 days.",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("13.4-INV-01", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.4-INV-02", "VAT"),
            InvalidCondition("13.4-INV-03", "Cash-back portion"),
            InvalidCondition("13.4-INV-04", "AFD transaction"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.4-DOC-01", "Evidence from qualified entity (IP owner, customs, expert)", "counterfeit_evidence"),
            DocumentRequirement("13.4-DOC-02", "Date received or notified", "receipt_notification_date"),
            DocumentRequirement("13.4-DOC-03", "Description of merchandise", "merchandise_description"),
            DocumentRequirement("13.4-DOC-04", "Disposition of merchandise", "merchandise_disposition"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence merchandise is genuine",
        ],
        special_notes=[
            "Dispute applies even if cardholder hasn't received merchandise (if advised it's counterfeit)",
        ],
    ),
    # ── 13.5: Misrepresentation ──────────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_MISREPRESENTATION,
        name="Misrepresentation",
        description="Terms of sale misrepresented by Merchant.",
        rule_section="11.10.6",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE],
        triggers=[
            "Terms of sale misrepresented by Merchant",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            max_calendar_days=540,
            description="120 days from Processing Date or receipt date. OR 60 days from first notification with ongoing negotiations. Max 540 days.",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("13.5-INV-01", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.5-INV-02", "VAT"),
            InvalidCondition("13.5-INV-03", "Quality-only dispute"),
            InvalidCondition("13.5-INV-04", "Cash-back portion"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.5-DOC-01", "Evidence of misrepresentation", "misrepresentation_evidence"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "Proof terms weren't misrepresented",
            "For trial/promo: proof cardholder expressly agreed + 7-day pre-notification",
        ],
        special_notes=[
            "Applies to: trial/promotional subscriptions, timeshare resellers, debt consolidation/credit repair",
            "Also: tech support with malicious software, business opportunities, fund recovery scams",
            "Also: outbound telemarketing, investment services refusing withdrawals",
        ],
    ),
    # ── 13.6: Credit Not Processed ───────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_CREDIT_NOT_PROCESSED,
        name="Credit Not Processed",
        description="Cardholder received credit/voided receipt that wasn't processed.",
        rule_section="11.10.7",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Cardholder received credit/voided receipt that wasn't processed",
            "OR: ATM Adjustment disputed because original transaction cancelled/reversed",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="credit_receipt_date",
            wait_days_before=15,
            max_calendar_days=540,
            description="Wait 15 cal days from Credit Receipt date. Then 120 days from Credit Receipt date. Max 540 days.",
        ),
        dispute_amount_rule="Credit amount not processed",
        invalid_conditions=[
            InvalidCondition("13.6-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("13.6-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.6-INV-03", "Cash-back portion"),
            InvalidCondition("13.6-INV-04", "AFD transaction"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.6-DOC-01", "Copy of Credit Transaction Receipt, voided receipt, or other proof", "credit_receipt_proof"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence credit was processed",
        ],
    ),
    # ── 13.7: Cancelled Merchandise/Services ─────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_CANCELLED,
        name="Cancelled Merchandise/Services",
        description="Cardholder cancelled/returned; Merchant didn't process credit or misapplied return policy.",
        rule_section="11.10.8",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE],
        triggers=[
            "Cardholder cancelled or returned merchandise/services",
            "OR: Cancelled timeshare",
            "OR: Cancelled Guaranteed Reservation",
            "Merchant didn't process credit",
            "OR: Merchant didn't properly disclose or apply return/cancellation policy",
        ],
        prerequisites=[
            "Cardholder must attempt to resolve with Merchant first",
            "Merchant responsible for customs in own country",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            wait_days_before=15,
            max_calendar_days=540,
            description="Wait 15 cal days from return/cancellation. Then 120 days from Processing Date or expected receipt date. Max 540 days.",
        ),
        dispute_amount_rule="Limited to unused portion or returned value",
        invalid_conditions=[
            InvalidCondition("13.7-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("13.7-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("13.7-INV-03", "Quality dispute (unless Credit Receipt provided)"),
            InvalidCondition("13.7-INV-04", "VAT (unless Credit Receipt provided)"),
            InvalidCondition("13.7-INV-05", "Customs charges (non-Merchant country)"),
            InvalidCondition("13.7-INV-06", "Cash-back portion"),
            InvalidCondition("13.7-INV-07", "Cardholder states transaction is fraudulent"),
            InvalidCondition("13.7-INV-08", "AFD transaction"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.7-DOC-01", "Cancellation/return details", "cancellation_details"),
            DocumentRequirement("13.7-DOC-02", "Evidence of Merchant return policy", "return_policy_evidence", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence of properly disclosed return/cancellation policy",
            "Proof cardholder received the policy",
        ],
        special_notes=[
            "Timeshare: within 14 days of contract",
            "Guaranteed Reservation: cancelled per policy or within 24 hours of confirmation",
            "No-Show limited to 1 day",
            "Europe: 14-day off-premises/distance selling cancellation right",
        ],
    ),
    # ── 13.8: Original Credit Transaction Not Accepted ───────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_OCT_NOT_ACCEPTED,
        name="Original Credit Transaction Not Accepted",
        description="OCT not accepted because recipient refused or OCTs prohibited by law.",
        rule_section="11.10.9",
        environments=[TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Original Credit Transaction not accepted: recipient refused",
            "OR: OCTs prohibited by law/regulation",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from OCT Processing Date",
        ),
        dispute_amount_rule="Full OCT amount",
        invalid_conditions=[
            InvalidCondition("13.8-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.8-DOC-01", "Certification: OCT not allowed by law OR recipient refused", "oct_refusal_certification"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "Evidence OCT was properly accepted",
        ],
    ),
    # ── 13.9: Non-Receipt of Cash at ATM ─────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.CONSUMER_ATM_NON_RECEIPT,
        name="Non-Receipt of Cash at ATM",
        description="Cardholder participated but didn't receive cash or received partial amount.",
        rule_section="11.10.10",
        environments=[TransactionEnvironment.ATM],
        triggers=[
            "Cardholder participated but didn't receive cash",
            "OR: Received partial amount",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
            regional_overrides={
                "EG_ATM": "10 calendar days (Egypt domestic ATM)",
                "IN_ATM": "6 calendar days (India domestic ATM)",
            },
        ),
        dispute_amount_rule="Limited to amount NOT received",
        invalid_conditions=[
            InvalidCondition("13.9-INV-01", "Cash-In transaction"),
            InvalidCondition("13.9-INV-02", "Cash-Out transaction"),
            InvalidCondition("13.9-INV-03", "Cardholder states transaction is fraudulent"),
            InvalidCondition("13.9-INV-04", "Transaction processed more than once (use 12.6)"),
        ],
        documentation_requirements=[
            DocumentRequirement("13.9-DOC-01", "Certification of non-receipt or partial receipt (including amount received)", "atm_non_receipt_certification"),
            DocumentRequirement("13.9-DOC-02", "Cardholder letter if 3+ disputes in 30-day period", "cardholder_letter", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Issuer pre-arbitration",
                actor="issuer",
                evidence_types=[
                    "New documentation",
                    "Changed dispute condition",
                ],
            ),
        ],
        dispute_response_rights=[
            "ATM Cash Disbursement Transaction record: credential, time/sequence number, successful indicator",
        ],
    ),
]
