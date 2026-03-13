"""Category 12: Processing Errors — Dispute condition rules (12.2 through 12.7).

Encoded from Visa Core Rules Chapter 11, Section 11.9.
"""

from __future__ import annotations

from src.models.enums import DisputeCondition, TransactionEnvironment
from src.rules.models import (
    DisputeConditionRule,
    DocumentRequirement,
    InvalidCondition,
    TimeLimitRule,
)

PROCESSING_ERROR_CONDITIONS: list[DisputeConditionRule] = [
    # ── 12.2: Incorrect Transaction Code ─────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_INCORRECT_CODE,
        name="Incorrect Transaction Code",
        description="Credit processed as debit, debit as credit, or credit refund instead of reversal/adjustment.",
        rule_section="11.9.1",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Credit processed as debit",
            "Debit processed as credit",
            "Credit refund processed instead of reversal/adjustment",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date (or Processing Date of credit refund)",
        ),
        dispute_amount_rule="DOUBLE the transaction amount if credit<>debit swap; difference between credit refund and original debit for refund errors",
        invalid_conditions=[
            InvalidCondition("12.2-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
        ],
        documentation_requirements=[],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "Transaction Receipt proving code was correct",
            "Reversal/credit not addressed in Dispute",
        ],
    ),
    # ── 12.3: Incorrect Currency ─────────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_INCORRECT_CURRENCY,
        name="Incorrect Currency",
        description="Transaction currency different than transmitted or DCC without cardholder consent.",
        rule_section="11.9.2",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Transaction currency different than transmitted via VisaNet",
            "OR: DCC occurred without cardholder's express agreement",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Entire transaction amount; pre-arb limited to DCC difference",
        invalid_conditions=[
            InvalidCondition("12.3-INV-01", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("12.3-INV-02", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("12.3-INV-03", "USD ATM transaction outside US on Plus System (excluding DCC)"),
        ],
        documentation_requirements=[],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "For DCC: Acquirer may reprocess in local currency (excluding DCC fees)",
            "OR: Resubmit as first presentment",
        ],
    ),
    # ── 12.4: Incorrect Account Number ───────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_INCORRECT_ACCOUNT,
        name="Incorrect Account Number",
        description="Transaction processed using incorrect Payment Credential.",
        rule_section="11.9.3",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ATM],
        triggers=[
            "Transaction processed using incorrect Payment Credential",
            "OR: ATM Deposit Adjustment with incorrect credential",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Full transaction amount",
        invalid_conditions=[
            InvalidCondition("12.4-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("12.4-INV-02", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("12.4-INV-03", "Credential not on file but Imprint/Auth obtained"),
            InvalidCondition("12.4-INV-04", "Chip-initiated with valid Cryptogram"),
            InvalidCondition("12.4-INV-05", "Mobility & Transport transaction"),
            InvalidCondition("12.4-INV-06", "Mobile Push Payment", "is_mobile_push_payment", "True"),
        ],
        documentation_requirements=[],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "Evidence credential was correct",
        ],
    ),
    # ── 12.5: Incorrect Amount ───────────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_INCORRECT_AMOUNT,
        name="Incorrect Amount",
        description="Transaction amount incorrect; addition/transposition error.",
        rule_section="11.9.4",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ATM],
        triggers=[
            "Transaction amount is incorrect",
            "Addition or transposition error",
            "OR: ATM Deposit Adjustment amount incorrect",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Limited to DIFFERENCE between correct and incorrect amounts. Handwritten amount prevails over imprinted.",
        invalid_conditions=[
            InvalidCondition("12.5-INV-01", "ATM Cash Disbursement"),
            InvalidCondition("12.5-INV-02", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("12.5-INV-03", "Straight Through Processing", "is_straight_through_processing", "True"),
            InvalidCondition("12.5-INV-04", "T&E price difference"),
            InvalidCondition("12.5-INV-05", "No-Show Transaction"),
            InvalidCondition("12.5-INV-06", "Advance Payment"),
            InvalidCondition("12.5-INV-07", "Transaction where Merchant has right to alter amount"),
        ],
        documentation_requirements=[],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "Transaction receipt proving amount was correct",
            "Evidence Merchant had right to alter amount",
        ],
    ),
    # ── 12.6: Duplicate Processing / Paid by Other Means ─────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_DUPLICATE,
        name="Duplicate Processing / Paid by Other Means",
        description="Single transaction processed more than once, or cardholder paid by other means.",
        rule_section="11.9.5",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.ATM],
        triggers=[
            "Single transaction processed more than once (same credential, date, amount)",
            "OR: Cardholder paid by other means",
            "OR: ATM Deposit Adjustment processed more than once",
        ],
        prerequisites=[
            "For paid-by-other-means: Cardholder must attempt to resolve with Merchant first",
        ],
        time_limit=TimeLimitRule(
            calendar_days=120,
            from_event="transaction_processing_date",
            description="120 calendar days from Transaction Processing Date",
            regional_overrides={
                "EG_ATM": "10 calendar days (Egypt domestic ATM)",
                "IN_ATM": "6 calendar days (India domestic ATM)",
            },
        ),
        dispute_amount_rule="Duplicate transaction amount; or amount paid by other means",
        invalid_conditions=[
            InvalidCondition("12.6-INV-01", "Payments to different merchants (unless evidence of payment pass-through)"),
        ],
        documentation_requirements=[
            DocumentRequirement("12.6-DOC-01", "For duplicate: date + ARN of valid transaction", "valid_transaction_reference"),
            DocumentRequirement("12.6-DOC-02", "For other means: evidence merchant received other payment", "other_payment_evidence", is_mandatory=False),
        ],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "Evidence transactions are for different goods/services",
            "Evidence other payment was not received",
        ],
    ),
    # ── 12.7: Invalid Data ───────────────────────────────────────────────
    DisputeConditionRule(
        condition=DisputeCondition.PROC_INVALID_DATA,
        name="Invalid Data",
        description="Authorization obtained using invalid/incorrect data; MCC mismatch between auth and clearing.",
        rule_section="11.9.6",
        environments=[TransactionEnvironment.CARD_PRESENT, TransactionEnvironment.CARD_ABSENT],
        triggers=[
            "Authorization obtained using invalid/incorrect data",
            "OR: MCC mismatch between authorization request and clearing record",
        ],
        prerequisites=[],
        time_limit=TimeLimitRule(
            calendar_days=75,
            from_event="transaction_processing_date",
            description="75 calendar days from Transaction Processing Date",
        ),
        dispute_amount_rule="Entire transaction amount",
        invalid_conditions=[
            InvalidCondition("12.7-INV-01", "Mobile Push Payment", "is_mobile_push_payment", "True"),
            InvalidCondition("12.7-INV-02", "ATM Cash Disbursement"),
        ],
        documentation_requirements=[
            DocumentRequirement("12.7-DOC-01", "Certification that auth would have been declined if valid data provided + explanation why", "invalid_data_certification"),
        ],
        pre_arbitration_rights=[],
        dispute_response_rights=[
            "Evidence data was correct",
        ],
    ),
]
