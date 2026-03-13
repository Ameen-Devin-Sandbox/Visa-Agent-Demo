"""Category 10: Fraud — Dispute condition rules (10.1 through 10.5).

Encoded from Visa Core Rules Chapter 11, Section 11.7.
"""

from __future__ import annotations

from src.models.enums import DisputeCondition, Region, TransactionEnvironment
from src.rules.models import (
    DisputeConditionRule,
    DocumentRequirement,
    InvalidCondition,
    PreArbitrationRight,
    TimeLimitRule,
)

FRAUD_CONDITIONS: list[DisputeConditionRule] = [
    # ── 10.1: EMV Liability Shift Counterfeit Fraud ──────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.FRAUD_EMV_COUNTERFEIT,
        name="EMV Liability Shift Counterfeit Fraud",
        description="Counterfeit card used in card-present environment where chip technology should have prevented fraud.",
        rule_section="11.7.2",
        environments=[TransactionEnvironment.CARD_PRESENT],
        triggers=[
            "Card is a Chip Card",
            "Transaction did not take place at a Chip-Reading Device",
            "OR: Chip-initiated but Acquirer did not transmit Full-Chip Data in auth request",
            "OR: Approved offline without Full-Chip Data in Clearing Record",
        ],
        prerequisites=[
            "Issuer must report Fraud Activity to Visa using fraud type code 4 (counterfeit)",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("10.1-INV-01", "Chip-initiated transaction (full chip data present)", "is_chip_initiated", "True"),
            InvalidCondition("10.1-INV-02", "Emergency Cash Disbursement", "is_emergency_cash", "True"),
            InvalidCondition("10.1-INV-03", "Fallback Transaction"),
            InvalidCondition("10.1-INV-04", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("10.1-INV-05", "POS Entry Mode 90 without chip service code"),
            InvalidCondition("10.1-INV-06", "CVV not verified or CVV verification failed"),
            InvalidCondition("10.1-INV-07", "Transaction approved on credential with reported Fraud Activity (except codes C, D)"),
            InvalidCondition("10.1-INV-08", "Delayed charge with proper linking (indicator 3902 + Transaction ID + Electronic Imprint)"),
            InvalidCondition("10.1-INV-09", "Visa Commercial Choice Omni Product"),
            InvalidCondition("10.1-INV-10", "Token transaction (excluding Europe)"),
        ],
        documentation_requirements=[
            DocumentRequirement("10.1-DOC-01", "Cardholder denies authorization/participation", "cardholder_certification"),
            DocumentRequirement("10.1-DOC-02", "For key-entered: certification Card is Chip Card", "chip_card_certification", condition_notes="Only if key-entered"),
            DocumentRequirement("10.1-DOC-03", "Explanation if fraud type changed from original", "fraud_type_explanation", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit/reversal not addressed in Dispute",
                    "Dispute is invalid (per invalid conditions)",
                    "Cardholder no longer disputes the transaction",
                    "Delayed charge evidence",
                ],
                regional_notes={"US": "Compelling Evidence also allowed"},
            ),
        ],
    ),
    # ── 10.2: EMV Liability Shift Non-Counterfeit Fraud ──────────────────
    DisputeConditionRule(
        condition=DisputeCondition.FRAUD_EMV_NON_COUNTERFEIT,
        name="EMV Liability Shift Non-Counterfeit Fraud",
        description="Lost/stolen/NRI card used in card-present environment with PIN-Preferring Chip Card.",
        rule_section="11.7.3",
        environments=[TransactionEnvironment.CARD_PRESENT],
        triggers=[
            "Card-present, non-counterfeit fraud (lost/stolen/NRI)",
            "Card is PIN-Preferring Chip Card",
            "Device not chip-reading, not EMV PIN-compliant, or Chip-initiated without online PIN and no Full-Chip Data",
        ],
        prerequisites=[
            "Issuer must report Fraud Activity using code 0 (lost), 1 (stolen), or 2 (NRI)",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("10.2-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("10.2-INV-02", "Contactless transaction", "is_contactless", "True"),
            InvalidCondition("10.2-INV-03", "Emergency Cash Disbursement", "is_emergency_cash", "True"),
            InvalidCondition("10.2-INV-04", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("10.2-INV-05", "Correctly processed at EMV PIN-Compliant device"),
            InvalidCondition("10.2-INV-06", "VEPS transaction"),
            InvalidCondition("10.2-INV-07", "Fallback Transaction"),
            InvalidCondition("10.2-INV-08", "Transaction on credential with reported Fraud Activity (except C, D)"),
            InvalidCondition("10.2-INV-09", "Visa Commercial Choice Omni Product"),
            InvalidCondition("10.2-INV-10", "Mobility & Transport transaction"),
            InvalidCondition("10.2-INV-11", "Delayed charge with proper linking"),
        ],
        documentation_requirements=[
            DocumentRequirement("10.2-DOC-01", "Certification: Card was PIN-Preferring Chip Card + cardholder denies", "cardholder_certification"),
            DocumentRequirement("10.2-DOC-02", "Explanation if fraud type changed from original", "fraud_type_explanation", is_mandatory=False),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit/reversal not addressed in Dispute",
                    "Dispute is invalid",
                    "Cardholder no longer disputes",
                    "Delayed charge proof",
                ],
            ),
        ],
    ),
    # ── 10.3: Other Fraud — Card-Present Environment ─────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.FRAUD_CARD_PRESENT,
        name="Other Fraud — Card-Present Environment",
        description="Cardholder denies authorization/participation in a key-entered transaction in card-present environment.",
        rule_section="11.7.4",
        environments=[TransactionEnvironment.CARD_PRESENT],
        triggers=[
            "Cardholder denies authorization/participation",
            "Key-entered transaction in card-present environment",
        ],
        prerequisites=[
            "Issuer must report Fraud Activity to Visa",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("10.3-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("10.3-INV-02", "Emergency Cash Disbursement", "is_emergency_cash", "True"),
            InvalidCondition("10.3-INV-03", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("10.3-INV-04", "Transaction on credential with reported Fraud Activity (except C, D)"),
            InvalidCondition("10.3-INV-05", "Visa Commercial Choice Omni Product"),
            InvalidCondition("10.3-INV-06", "Mobility & Transport Transaction"),
            InvalidCondition("10.3-INV-07", "US: AFD at Chip-Reading Device"),
            InvalidCondition("10.3-INV-08", "Electronic Imprint obtained", "electronic_imprint", "True"),
            InvalidCondition("10.3-INV-09", "Delayed charge with proper linking"),
            InvalidCondition("10.3-INV-10", "Fraud type codes 3 (fraudulent application), C (misrepresentation), D (manipulation)"),
        ],
        documentation_requirements=[
            DocumentRequirement("10.3-DOC-01", "Certification that cardholder denies authorization/participation", "cardholder_certification"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Dispute is invalid",
                    "Credit/reversal not addressed",
                    "Cardholder no longer disputes",
                    "Delayed charge proof",
                    "Evidence of Electronic Imprint",
                ],
                regional_notes={"US": "Compelling Evidence also allowed"},
            ),
        ],
    ),
    # ── 10.4: Other Fraud — Card-Absent Environment ──────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.FRAUD_CARD_ABSENT,
        name="Other Fraud — Card-Absent Environment",
        description="Cardholder denies authorization/participation in card-absent environment transaction.",
        rule_section="11.7.5",
        environments=[TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ECOMMERCE, TransactionEnvironment.MAIL_PHONE],
        triggers=[
            "Cardholder denies authorization/participation in card-absent transaction",
        ],
        prerequisites=[
            "Issuer must report Fraud Activity to Visa",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("10.4-INV-01", "Emergency Cash Disbursement", "is_emergency_cash", "True"),
            InvalidCondition("10.4-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("10.4-INV-03", "Transaction on credential with reported Fraud Activity (except C, D)"),
            InvalidCondition("10.4-INV-04", ">35 disputes on same account in prior 120 calendar days", "disputes_on_account_last_120_days", "35", "greater_than"),
            InvalidCondition("10.4-INV-05", "Debt recovery under Mobility/Transport framework", effective_date="2026-04-18"),
            InvalidCondition("10.4-INV-06", "CVV2 result code U + CVV2 presence indicator 1, 2, or 9"),
            InvalidCondition("10.4-INV-07", "Delayed charge with indicator 3902 + Transaction ID linking + Electronic Imprint"),
            InvalidCondition("10.4-INV-08", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("10.4-INV-09", "Secure E-Commerce: ECI 5 + CAVV + Visa Secure EMV 3DS authentication"),
            InvalidCondition("10.4-INV-10", "Authenticated Payment Credential: ECI 5 + TAVV + approved CVM"),
            InvalidCondition("10.4-INV-11", "Non-Authenticated Security Txn: ECI 6 + CAVV + Attempt Response (excl. non-reloadable prepaid)"),
            InvalidCondition("10.4-INV-12", "Fraud type codes 3, C, D"),
            InvalidCondition("10.4-INV-13", "Visa Commercial Choice Omni Product"),
            InvalidCondition("10.4-INV-14", "Crypto/NFT where Cardholder deceived into sending to fraudulent recipient"),
            InvalidCondition("10.4-INV-15", "Compelling Evidence 3.0: Same credential in 2 prior undisputed txns >120 days with matching device/IP"),
            InvalidCondition("10.4-INV-16", "CVV2 presence indicator 1 + result N + Authorization approved"),
            InvalidCondition("10.4-INV-17", "US: Airline/railway with AVS Y + tickets mailed to billing address", region=Region.US),
            InvalidCondition("10.4-INV-18", "US/Canada/UK: AVS attempted + AVS Result Code U7"),
        ],
        documentation_requirements=[
            DocumentRequirement("10.4-DOC-01", "Certification that cardholder denies authorization/participation", "cardholder_certification"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Dispute is invalid",
                    "Credit/reversal not addressed",
                    "Cardholder no longer disputes",
                    "Compelling Evidence (Table 11-6, 16 item types)",
                    "Airline manifest matching cardholder name",
                    "CE 3.0 matching data",
                ],
            ),
        ],
        special_notes=[
            "US Domestic: Dispute applies regardless of ECI for MCCs 4829, 5967, 6051, 6540, 7801, 7802, 7995 (wire transfer, adult, crypto, stored value, gambling)",
            "This condition has the largest invalid disputes list in the Visa Rules",
        ],
    ),
    # ── 10.5: Visa Fraud Monitoring Program ──────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.FRAUD_VFMP,
        name="Visa Fraud Monitoring Program",
        description="Visa notified Issuer that transaction was identified by VFMP.",
        rule_section="11.7.6",
        environments=[
            TransactionEnvironment.CARD_PRESENT,
            TransactionEnvironment.CARD_ABSENT,
            TransactionEnvironment.ECOMMERCE,
            TransactionEnvironment.ATM,
        ],
        triggers=[
            "Visa notified Issuer that transaction was identified by VFMP",
            "Issuer has NOT already successfully disputed under another condition",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="vfmp_report_date",
            description="120 calendar days from date of VFMP report",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[],  # No invalid disputes for 10.5
        documentation_requirements=[],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit/reversal not addressed in Dispute",
                    "Dispute is invalid",
                ],
            ),
        ],
        special_notes=[
            "ONLY condition allowing a second dispute on the same transaction",
        ],
    ),
]
