"""Category 11: Authorization — Dispute condition rules (11.1 through 11.3).

Encoded from Visa Core Rules Chapter 11, Section 11.8.
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

AUTHORIZATION_CONDITIONS: list[DisputeConditionRule] = [
    # ── 11.1: Card Recovery Bulletin ─────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.AUTH_CARD_RECOVERY,
        name="Card Recovery Bulletin",
        description="Transaction below Floor Limit, Merchant didn't obtain Authorization, Account Number was on CRB.",
        rule_section="11.8.1",
        environments=[TransactionEnvironment.CARD_PRESENT],
        triggers=[
            "Transaction below Floor Limit",
            "Merchant did not obtain Authorization",
            "Account Number listed on Card Recovery Bulletin on Transaction Date",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=75,
            from_event="transaction_processing_date",
            description="75 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("11.1-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("11.1-INV-02", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("11.1-INV-03", "Contactless-Only device"),
            InvalidCondition("11.1-INV-04", "Chip-Reading Device + EMV liability shift qualifying"),
        ],
        documentation_requirements=[],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit not addressed in Dispute",
                    "Dispute is invalid",
                    "T&E: CRB listing didn't apply on check-in/rental/embarkation date",
                ],
            ),
        ],
        special_notes=[
            "Being phased out — effective through 23 October 2026",
        ],
    ),
    # ── 11.2: Declined Authorization ─────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.AUTH_DECLINED,
        name="Declined Authorization",
        description="Authorization Request received Decline or Pickup Response, but Merchant completed the transaction.",
        rule_section="11.8.2",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Authorization Request received Decline or Pickup Response",
            "Merchant completed the transaction despite decline",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=75,
            from_event="transaction_processing_date",
            description="75 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("11.2-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("11.2-INV-02", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("11.2-INV-03", "Transaction where auth was obtained AFTER decline (except pickup codes 04, 07, 41, 43)"),
        ],
        documentation_requirements=[
            DocumentRequirement("11.2-DOC-01", "Certification: on Dispute Processing Date, account was flagged Credit Problem, Closed, or Fraud", "account_status_certification"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit not addressed",
                    "Dispute is invalid",
                ],
            ),
        ],
        special_notes=[
            "Mobility & Transport: valid for full amount if Decline was sent and txn amount exceeded specified threshold",
        ],
    ),
    # ── 11.3: No Authorization / Late Presentment ────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.AUTH_NO_AUTH_LATE,
        name="No Authorization / Late Presentment",
        description="Valid authorization required but not obtained, or obtained but transaction not processed within timeframe.",
        rule_section="11.8.3",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ATM],
        triggers=[
            "Valid authorization required but not obtained",
            "OR: Valid authorization obtained but transaction not processed within timeframe",
            "OR: Authorization not required and transaction not processed within timeframe",
            "OR: ATM Deposit Adjustment on closed/credit problem account >10 days after txn",
            "OR: ATM Cash Disbursement Adjustment with similar rules",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=75,
            from_event="transaction_processing_date",
            description="75 calendar days from Transaction Processing Date",
            regional_overrides={
                "IN_ATM": "ATM adjustment >4 days (India)",
                "NP_ATM": "ATM adjustment >3 days (Nepal)",
            },
        ),
        dispute_amount_rule="Full transaction amount; limited to amount above Floor Limit for chip-initiated offline-authorized; limited to unauthorized amount if partial auth obtained",
        invalid_conditions=[
            InvalidCondition("11.3-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("11.3-INV-02", "Credit transactions for Airlines/Transport MCCs (3000-3350, 4111, 4112, 4131, 4511)"),
            InvalidCondition("11.3-INV-03", "Europe: Visa Drive Card toll/parking transactions", region=Region.EUROPE),
        ],
        documentation_requirements=[
            DocumentRequirement("11.3-DOC-01", "Certification of account status (Credit Problem, Closed, Fraud) on Dispute Processing Date", "account_status_certification"),
        ],
        pre_arbitration_rights=[
            PreArbitrationRight(
                description="Acquirer pre-arbitration attempt",
                actor="acquirer",
                evidence_types=[
                    "Credit not addressed",
                    "Dispute is invalid",
                ],
            ),
        ],
    ),
]
