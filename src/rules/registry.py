"""Rules registry — central index of all encoded Visa dispute rules."""

from __future__ import annotations

from src.models.enums import DisputeCategory, DisputeCondition
from src.rules.categories.authorization import AUTHORIZATION_CONDITIONS
from src.rules.categories.consumer import CONSUMER_CONDITIONS
from src.rules.categories.fraud import FRAUD_CONDITIONS
from src.rules.categories.processing_errors import PROCESSING_ERROR_CONDITIONS
from src.rules.models import CompellingEvidenceItem, DisputeConditionRule

ALL_CONDITIONS: list[DisputeConditionRule] = (
    FRAUD_CONDITIONS
    + AUTHORIZATION_CONDITIONS
    + PROCESSING_ERROR_CONDITIONS
    + CONSUMER_CONDITIONS
)

CONDITIONS_BY_CODE: dict[DisputeCondition, DisputeConditionRule] = {
    rule.condition: rule for rule in ALL_CONDITIONS
}

CONDITIONS_BY_CATEGORY: dict[DisputeCategory, list[DisputeConditionRule]] = {}
for rule in ALL_CONDITIONS:
    cat = rule.condition.category
    CONDITIONS_BY_CATEGORY.setdefault(cat, []).append(rule)

# ── Compelling Evidence (Table 11-6) ─────────────────────────────────────────
COMPELLING_EVIDENCE: list[CompellingEvidenceItem] = [
    CompellingEvidenceItem(
        item_number=1,
        description="Photo/email evidence linking person receiving merchandise to Cardholder",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=2,
        description="Card-Absent merchandise collected from Merchant: signed pick-up form, copy of ID, ID details",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=3,
        description="Card-Absent merchandise delivered to AVS match Y or M address (no signature required)",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=4,
        description="E-Commerce digital goods: description + date/time + 2+ of: IP/device location, Device ID, email, verified profile, website access, same device/Card",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
        sub_requirements=[
            "Description of merchandise downloaded",
            "Date and time of download",
            "PLUS 2 or more of: IP/device location, Device ID, email linked to profile, verified profile, accessed website after Transaction Date, same device/Card in undisputed transaction",
        ],
    ),
    CompellingEvidenceItem(
        item_number=5,
        description="Merchandise delivered to business address + Cardholder worked there at time of delivery",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=6,
        description="Mail/Phone Order: signed order form",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=7,
        description="Passenger transport: ticket received at billing address, boarding pass scanned, frequent flyer details, related transactions",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=8,
        description="T&E Transaction: loyalty program details + related additional non-disputed transactions",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=9,
        description="Virtual Card at Lodging: evidence of Issuer payment instruction via Visa Payables Automation",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=10,
        description="Card-Absent: 3+ of account/login ID, delivery address, device ID, email, IP, telephone matching undisputed transaction",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
        sub_requirements=[
            "3 or more of: account/login ID, delivery address, device ID, email address, IP address, telephone number",
            "Must match data from a prior undisputed transaction on the same Payment Credential",
        ],
    ),
    CompellingEvidenceItem(
        item_number=11,
        description="Transaction completed by household/family member",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=12,
        description="Non-disputed payments for same merchandise/service",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=13,
        description="Recurring Transaction: legally binding contract + Cardholder using merchandise/services + prior undisputed transaction",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
        sub_requirements=[
            "Legally binding contract",
            "Evidence Cardholder is using merchandise/services",
            "Prior undisputed transaction",
        ],
    ),
    CompellingEvidenceItem(
        item_number=14,
        description="Europe: Initial wallet transaction via Visa Secure, subsequent transactions had wallet-related data",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
    CompellingEvidenceItem(
        item_number=15,
        description="US Domestic Card-Present key-entered not at Chip-Reading Device: same Card in prior undisputed transaction, or copy of ID + receipt linking to ID",
        applicable_conditions=[DisputeCondition.FRAUD_EMV_COUNTERFEIT, DisputeCondition.FRAUD_CARD_PRESENT],
    ),
    CompellingEvidenceItem(
        item_number=16,
        description="Non-fiat currency/NFT: destination wallet, blockchain hash (searchable), prior approved similar transactions",
        applicable_conditions=[DisputeCondition.FRAUD_CARD_ABSENT],
    ),
]


def get_condition_rule(condition: DisputeCondition) -> DisputeConditionRule:
    """Look up the full rule for a dispute condition code."""
    rule = CONDITIONS_BY_CODE.get(condition)
    if rule is None:
        raise ValueError(f"Unknown dispute condition: {condition}")
    return rule


def get_conditions_for_category(category: DisputeCategory) -> list[DisputeConditionRule]:
    """Get all condition rules for a dispute category."""
    return CONDITIONS_BY_CATEGORY.get(category, [])


def get_compelling_evidence_for_condition(
    condition: DisputeCondition,
) -> list[CompellingEvidenceItem]:
    """Get applicable compelling evidence items for a condition."""
    return [ce for ce in COMPELLING_EVIDENCE if condition in ce.applicable_conditions]
