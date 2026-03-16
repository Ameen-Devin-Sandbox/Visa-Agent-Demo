"""Documentation and certification requirement validators.

Encodes the required documentation/certification for each dispute condition
as specified in Visa Core Rules Section 11.7-11.10.
"""

from dataclasses import dataclass

from src.models.dispute import DisputeCase
from src.models.enums import DisputeCondition, FraudTypeCode


@dataclass
class DocumentationRequirement:
    """A required document or certification for a dispute condition."""

    requirement_id: str
    description: str
    is_mandatory: bool
    rule_section: str
    condition: str


@dataclass
class DocumentationCheckResult:
    """Result of checking documentation requirements."""

    is_complete: bool
    met_requirements: list[str]
    missing_requirements: list[str]
    details: str


# Documentation requirements per dispute condition
DOCUMENTATION_REQUIREMENTS: dict[DisputeCondition, list[DocumentationRequirement]] = {
    DisputeCondition.EMV_COUNTERFEIT_FRAUD: [
        DocumentationRequirement(
            requirement_id="10.1_cert_denial",
            description="Certification that the Cardholder denies authorization of or participation in the Transaction",
            is_mandatory=True,
            rule_section="11.7.2.5",
            condition="10.1",
        ),
        DocumentationRequirement(
            requirement_id="10.1_cert_chip",
            description="For key-entered Transactions, certification that the Card is a Chip Card",
            is_mandatory=False,  # Only for key-entered
            rule_section="11.7.2.5",
            condition="10.1",
        ),
        DocumentationRequirement(
            requirement_id="10.1_fraud_report",
            description="Fraud Activity reported to Visa using fraud type code 4 (counterfeit)",
            is_mandatory=True,
            rule_section="11.7.2.2",
            condition="10.1",
        ),
    ],
    DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD: [
        DocumentationRequirement(
            requirement_id="10.2_cert_pin_chip",
            description="Certification that the Card was a PIN-Preferring Chip Card",
            is_mandatory=True,
            rule_section="11.7.3.5",
            condition="10.2",
        ),
        DocumentationRequirement(
            requirement_id="10.2_cert_denial",
            description="Certification that the Cardholder denies authorization of or participation in the Transaction",
            is_mandatory=True,
            rule_section="11.7.3.5",
            condition="10.2",
        ),
        DocumentationRequirement(
            requirement_id="10.2_fraud_report",
            description="Fraud Activity reported using fraud type code 0 (lost), 1 (stolen), or 2 (NRI)",
            is_mandatory=True,
            rule_section="11.7.3.2",
            condition="10.2",
        ),
    ],
    DisputeCondition.OTHER_FRAUD_CARD_PRESENT: [
        DocumentationRequirement(
            requirement_id="10.3_cert_denial",
            description="Certification that the Cardholder denies authorization of or participation in the Transaction",
            is_mandatory=True,
            rule_section="11.7.4.5",
            condition="10.3",
        ),
        DocumentationRequirement(
            requirement_id="10.3_fraud_report",
            description="Fraud Activity reported to Visa before initiating the Dispute",
            is_mandatory=True,
            rule_section="11.7.4.2",
            condition="10.3",
        ),
    ],
    DisputeCondition.OTHER_FRAUD_CARD_ABSENT: [
        DocumentationRequirement(
            requirement_id="10.4_cert_denial",
            description="Certification that the Cardholder denies authorization of or participation in the Transaction",
            is_mandatory=True,
            rule_section="11.7.5.5",
            condition="10.4",
        ),
        DocumentationRequirement(
            requirement_id="10.4_fraud_report",
            description="Fraud Activity reported to Visa before initiating the Dispute",
            is_mandatory=True,
            rule_section="11.7.5.2",
            condition="10.4",
        ),
    ],
    DisputeCondition.CARD_RECOVERY_BULLETIN: [
        DocumentationRequirement(
            requirement_id="11.1_crb_listing",
            description="Evidence that the Card was listed on the Card Recovery Bulletin",
            is_mandatory=True,
            rule_section="11.8.1.5",
            condition="11.1",
        ),
    ],
    DisputeCondition.DECLINED_AUTHORIZATION: [
        DocumentationRequirement(
            requirement_id="11.2_decline_record",
            description="Evidence of the declined authorization response",
            is_mandatory=True,
            rule_section="11.8.2.5",
            condition="11.2",
        ),
    ],
    DisputeCondition.NO_AUTHORIZATION: [
        DocumentationRequirement(
            requirement_id="11.3_no_auth",
            description="Evidence that no valid authorization was obtained or presentment was late",
            is_mandatory=True,
            rule_section="11.8.3.5",
            condition="11.3",
        ),
    ],
    DisputeCondition.INCORRECT_TRANSACTION_CODE: [
        DocumentationRequirement(
            requirement_id="12.2_incorrect_code",
            description="Description of the correct Transaction code and why the submitted code is incorrect",
            is_mandatory=True,
            rule_section="11.9.1.5",
            condition="12.2",
        ),
    ],
    DisputeCondition.INCORRECT_CURRENCY: [
        DocumentationRequirement(
            requirement_id="12.3_incorrect_currency",
            description="Evidence of the correct currency for the Transaction",
            is_mandatory=True,
            rule_section="11.9.2.5",
            condition="12.3",
        ),
    ],
    DisputeCondition.INCORRECT_ACCOUNT_NUMBER: [
        DocumentationRequirement(
            requirement_id="12.4_incorrect_account",
            description="Evidence that the incorrect account number was used",
            is_mandatory=True,
            rule_section="11.9.3.5",
            condition="12.4",
        ),
    ],
    DisputeCondition.INCORRECT_AMOUNT: [
        DocumentationRequirement(
            requirement_id="12.5_incorrect_amount",
            description="Evidence of the correct Transaction amount",
            is_mandatory=True,
            rule_section="11.9.4.5",
            condition="12.5",
        ),
    ],
    DisputeCondition.DUPLICATE_PROCESSING: [
        DocumentationRequirement(
            requirement_id="12.6_duplicate",
            description="Evidence that the Transaction was processed more than once or paid by other means",
            is_mandatory=True,
            rule_section="11.9.5.5",
            condition="12.6",
        ),
    ],
    DisputeCondition.INVALID_DATA: [
        DocumentationRequirement(
            requirement_id="12.7_invalid_data",
            description="Description of the invalid data in the Transaction",
            is_mandatory=True,
            rule_section="11.9.6.5",
            condition="12.7",
        ),
    ],
    DisputeCondition.MERCHANDISE_NOT_RECEIVED: [
        DocumentationRequirement(
            requirement_id="13.1_not_received",
            description="Cardholder statement that merchandise/services were not received",
            is_mandatory=True,
            rule_section="11.10.2.5",
            condition="13.1",
        ),
        DocumentationRequirement(
            requirement_id="13.1_expected_date",
            description="Expected delivery date or service date",
            is_mandatory=True,
            rule_section="11.10.2.5",
            condition="13.1",
        ),
    ],
    DisputeCondition.CANCELLED_RECURRING: [
        DocumentationRequirement(
            requirement_id="13.2_cancellation",
            description="Evidence that the recurring Transaction was cancelled",
            is_mandatory=True,
            rule_section="11.10.3.5",
            condition="13.2",
        ),
        DocumentationRequirement(
            requirement_id="13.2_cancel_date",
            description="Date of cancellation",
            is_mandatory=True,
            rule_section="11.10.3.5",
            condition="13.2",
        ),
    ],
    DisputeCondition.NOT_AS_DESCRIBED: [
        DocumentationRequirement(
            requirement_id="13.3_description",
            description="Description of how the merchandise/services differ from what was described",
            is_mandatory=True,
            rule_section="11.10.4.5",
            condition="13.3",
        ),
        DocumentationRequirement(
            requirement_id="13.3_attempt_resolve",
            description="Evidence that the Cardholder attempted to resolve with the Merchant",
            is_mandatory=True,
            rule_section="11.10.4.5",
            condition="13.3",
        ),
    ],
    DisputeCondition.COUNTERFEIT_MERCHANDISE: [
        DocumentationRequirement(
            requirement_id="13.4_counterfeit_evidence",
            description="Evidence that the merchandise is counterfeit",
            is_mandatory=True,
            rule_section="11.10.5.5",
            condition="13.4",
        ),
    ],
    DisputeCondition.MISREPRESENTATION: [
        DocumentationRequirement(
            requirement_id="13.5_misrep_description",
            description="Description of the misrepresentation",
            is_mandatory=True,
            rule_section="11.10.6.5",
            condition="13.5",
        ),
    ],
    DisputeCondition.CREDIT_NOT_PROCESSED: [
        DocumentationRequirement(
            requirement_id="13.6_credit_evidence",
            description="Evidence that a credit was expected but not processed",
            is_mandatory=True,
            rule_section="11.10.7.5",
            condition="13.6",
        ),
    ],
    DisputeCondition.CANCELLED_MERCHANDISE: [
        DocumentationRequirement(
            requirement_id="13.7_cancellation",
            description="Evidence of cancellation or return of merchandise/services",
            is_mandatory=True,
            rule_section="11.10.8.5",
            condition="13.7",
        ),
    ],
    DisputeCondition.OCT_NOT_ACCEPTED: [
        DocumentationRequirement(
            requirement_id="13.8_oct_evidence",
            description="Evidence that the Original Credit Transaction was not accepted",
            is_mandatory=True,
            rule_section="11.10.9.5",
            condition="13.8",
        ),
    ],
    DisputeCondition.NON_RECEIPT_CASH_ATM: [
        DocumentationRequirement(
            requirement_id="13.9_atm_evidence",
            description="Evidence that cash was not received at the ATM",
            is_mandatory=True,
            rule_section="11.10.10.5",
            condition="13.9",
        ),
    ],
}

# Cardholder letter requirements for Category 10 (Fraud)
CATEGORY_10_LETTER_REQUIREMENTS = [
    "Cardholder's complete or partial Payment Credential",
    "Merchant name(s)",
    "Transaction amount(s)",
]

# Cardholder letter requirements for Category 13 (Consumer Disputes)
CATEGORY_13_LETTER_REQUIREMENTS = [
    "Cardholder's complete or partial Payment Credential",
    "Merchant name(s)",
    "Transaction amount(s)",
    "Description of dispute reason",
]


def check_fraud_type_code_requirement(case: DisputeCase) -> DocumentationCheckResult:
    """Check that the correct fraud type code was reported for Category 10 conditions.

    Per Section 11.7.2.2: Before initiating a Dispute, an Issuer must report
    the Fraud Activity to Visa using the appropriate fraud type code.
    """
    if case.condition is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["dispute_condition_not_assigned"],
            details="Cannot check fraud type code: no dispute condition assigned",
        )

    required_codes: dict[DisputeCondition, list[FraudTypeCode]] = {
        DisputeCondition.EMV_COUNTERFEIT_FRAUD: [FraudTypeCode.COUNTERFEIT],
        DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD: [
            FraudTypeCode.LOST,
            FraudTypeCode.STOLEN,
            FraudTypeCode.NOT_RECEIVED,
        ],
    }

    if case.condition not in required_codes:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=["no_fraud_code_required"],
            missing_requirements=[],
            details="No specific fraud type code required for this condition",
        )

    allowed = required_codes[case.condition]
    if case.fraud_type_code is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["fraud_type_code"],
            details=f"Fraud type code not reported. Required: {[c.value for c in allowed]}",
        )

    if case.fraud_type_code in allowed:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=["fraud_type_code"],
            missing_requirements=[],
            details=f"Correct fraud type code reported: {case.fraud_type_code.value}",
        )

    return DocumentationCheckResult(
        is_complete=False,
        met_requirements=[],
        missing_requirements=["fraud_type_code_mismatch"],
        details=(
            f"Incorrect fraud type code: {case.fraud_type_code.value}. "
            f"Required: {[c.value for c in allowed]}"
        ),
    )


def check_documentation_requirements(case: DisputeCase) -> DocumentationCheckResult:
    """Check all documentation requirements for a dispute case.

    Validates that all mandatory documentation and certifications
    have been provided for the assigned dispute condition.
    """
    if case.condition is None:
        return DocumentationCheckResult(
            is_complete=False,
            met_requirements=[],
            missing_requirements=["condition_not_assigned"],
            details="Cannot check documentation: no dispute condition assigned",
        )

    requirements = DOCUMENTATION_REQUIREMENTS.get(case.condition, [])
    if not requirements:
        return DocumentationCheckResult(
            is_complete=True,
            met_requirements=[],
            missing_requirements=[],
            details=f"No specific documentation requirements for {case.condition.value}",
        )

    met: list[str] = []
    missing: list[str] = []

    # Check if issuer certification is provided (covers most certification requirements)
    has_certification = case.issuer_certification is not None
    has_cardholder_letter = case.cardholder.signed_letter_provided
    has_evidence = len(case.evidence) > 0

    for req in requirements:
        if not req.is_mandatory:
            continue

        # Simple heuristic: check if we have the general type of documentation
        if "certification" in req.description.lower() or "certif" in req.requirement_id:
            if has_certification or has_cardholder_letter:
                met.append(req.requirement_id)
            else:
                missing.append(req.requirement_id)
        elif "fraud" in req.requirement_id.lower() and "report" in req.requirement_id.lower():
            if case.fraud_type_code is not None:
                met.append(req.requirement_id)
            else:
                missing.append(req.requirement_id)
        elif has_evidence:
            met.append(req.requirement_id)
        else:
            missing.append(req.requirement_id)

    is_complete = len(missing) == 0

    return DocumentationCheckResult(
        is_complete=is_complete,
        met_requirements=met,
        missing_requirements=missing,
        details=(
            f"Documentation check: {len(met)} met, {len(missing)} missing"
            if missing
            else "All documentation requirements met"
        ),
    )
