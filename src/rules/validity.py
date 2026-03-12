"""Dispute validity checking logic.

Encodes the invalid dispute conditions from Visa Core Rules Section 11.7-11.10.
Each dispute condition has specific circumstances that make a dispute invalid.
"""

from dataclasses import dataclass
from datetime import datetime

from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    DisputeCondition,
    Region,
    TransactionEnvironment,
)


@dataclass
class ValidityCheckResult:
    """Result of a dispute validity check."""

    is_valid: bool
    reason: str
    rule_section: str
    condition_checked: str


def check_condition_10_1_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 10.1: EMV Liability Shift Counterfeit Fraud.

    Per Section 11.7.2.3, a dispute is invalid for:
    - Chip-initiated transactions
    - Emergency Cash Disbursements
    - Fallback Transactions
    - Mobile Push Payment Transactions
    - POS Entry Mode 90 with non-chip service code
    - CVV present but not verified or failed
    - Transaction approved with previously reported fraud credential
    - Token transactions (All excluding Europe)
    - Delayed charge transactions with specific conditions (effective Oct 2025)
    - Visa Commercial Choice Omni Product Transactions
    """
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.is_chip_initiated:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Chip-initiated transaction",
                rule_section="11.7.2.3",
                condition_checked="chip_initiated",
            )
        )

    if txn.is_emergency_cash_disbursement:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Emergency Cash Disbursement",
                rule_section="11.7.2.3",
                condition_checked="emergency_cash_disbursement",
            )
        )

    if txn.is_fallback_transaction:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Fallback Transaction",
                rule_section="11.7.2.3",
                condition_checked="fallback_transaction",
            )
        )

    if txn.is_mobile_push_payment:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Mobile Push Payment Transaction",
                rule_section="11.7.2.3",
                condition_checked="mobile_push_payment",
            )
        )

    if txn.cvv_present and (txn.cvv_verified is None or not txn.cvv_verified):
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: CVV present but verification not performed or failed",
                rule_section="11.7.2.3",
                condition_checked="cvv_verification_failed",
            )
        )

    if txn.is_token_transaction and txn.region != Region.EUROPE:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Token transaction (All excluding Europe)",
                rule_section="11.7.2.3",
                condition_checked="token_transaction_non_europe",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 10.1",
                rule_section="11.7.2.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_10_2_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 10.2: EMV Liability Shift Non-Counterfeit Fraud.

    Per Section 11.7.3.3, invalid for:
    - ATM Cash Disbursements
    - Contactless Transactions
    - Emergency Cash Disbursement Transactions
    - Mobile Push Payment Transactions
    - Correctly processed at EMV PIN-Compliant device
    - VEPS Transactions
    - Fallback Transactions
    - Approved with previously reported fraud credential
    - Visa Commercial Choice Omni Product Transactions
    - Mobility and Transport Transactions
    - Delayed charge with specific conditions (effective Oct 2025)
    """
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.environment == TransactionEnvironment.ATM:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: ATM Cash Disbursement",
                rule_section="11.7.3.3",
                condition_checked="atm_cash_disbursement",
            )
        )

    if txn.is_contactless:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Contactless Transaction",
                rule_section="11.7.3.3",
                condition_checked="contactless",
            )
        )

    if txn.is_emergency_cash_disbursement:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Emergency Cash Disbursement",
                rule_section="11.7.3.3",
                condition_checked="emergency_cash_disbursement",
            )
        )

    if txn.is_mobile_push_payment:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Mobile Push Payment Transaction",
                rule_section="11.7.3.3",
                condition_checked="mobile_push_payment",
            )
        )

    if txn.is_veps_transaction:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: VEPS Transaction",
                rule_section="11.7.3.3",
                condition_checked="veps_transaction",
            )
        )

    if txn.is_fallback_transaction:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Fallback Transaction",
                rule_section="11.7.3.3",
                condition_checked="fallback_transaction",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 10.2",
                rule_section="11.7.3.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_10_3_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 10.3: Other Fraud - Card-Present Environment."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.environment != TransactionEnvironment.CARD_PRESENT:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Transaction was not in Card-Present Environment",
                rule_section="11.7.4.3",
                condition_checked="not_card_present",
            )
        )

    if txn.is_mobile_push_payment:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Mobile Push Payment Transaction",
                rule_section="11.7.4.3",
                condition_checked="mobile_push_payment",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 10.3",
                rule_section="11.7.4.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_10_4_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 10.4: Other Fraud - Card-Absent Environment."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.environment == TransactionEnvironment.CARD_PRESENT:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Transaction was in Card-Present Environment (requires Card-Absent)",
                rule_section="11.7.5.3",
                condition_checked="card_present_not_allowed",
            )
        )

    if txn.is_mobile_push_payment:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Mobile Push Payment Transaction",
                rule_section="11.7.5.3",
                condition_checked="mobile_push_payment",
            )
        )

    if txn.three_d_secure_authenticated and txn.region != Region.EUROPE:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: 3-D Secure authenticated transaction (non-Europe)",
                rule_section="11.7.5.3",
                condition_checked="3ds_authenticated_non_europe",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 10.4",
                rule_section="11.7.5.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_11_1_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 11.1: Card Recovery Bulletin."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.is_mobile_push_payment:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Mobile Push Payment Transaction",
                rule_section="11.8.1.3",
                condition_checked="mobile_push_payment",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 11.1",
                rule_section="11.8.1.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_11_2_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 11.2: Declined Authorization."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.authorization_response_code and txn.authorization_response_code.startswith("0"):
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Authorization was approved, not declined",
                rule_section="11.8.2.3",
                condition_checked="authorization_approved",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 11.2",
                rule_section="11.8.2.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_11_3_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 11.3: No Authorization/Late Presentment."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.authorization_code:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Valid authorization code exists",
                rule_section="11.8.3.3",
                condition_checked="authorization_exists",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 11.3",
                rule_section="11.8.3.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_12_5_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 12.5: Incorrect Amount."""
    results: list[ValidityCheckResult] = []

    if case.dispute_amount is None:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: No dispute amount specified for incorrect amount claim",
                rule_section="11.9.4.3",
                condition_checked="no_dispute_amount",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 12.5",
                rule_section="11.9.4.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_12_6_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 12.6: Duplicate Processing/Paid by Other Means."""
    results: list[ValidityCheckResult] = []

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 12.6",
                rule_section="11.9.5.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_13_1_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 13.1: Merchandise/Services Not Received."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if txn.environment == TransactionEnvironment.ATM:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: ATM transactions use condition 13.9 instead",
                rule_section="11.10.2.3",
                condition_checked="atm_wrong_condition",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 13.1",
                rule_section="11.10.2.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_13_2_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 13.2: Cancelled Recurring Transaction."""
    results: list[ValidityCheckResult] = []
    txn = case.transaction

    if not txn.is_recurring:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: Transaction is not a recurring transaction",
                rule_section="11.10.3.3",
                condition_checked="not_recurring",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 13.2",
                rule_section="11.10.3.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


def check_condition_13_6_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Check invalid dispute conditions for 13.6: Credit Not Processed."""
    results: list[ValidityCheckResult] = []

    if not case.prior_credits:
        results.append(
            ValidityCheckResult(
                is_valid=False,
                reason="Dispute invalid: No evidence of expected credit that was not processed",
                rule_section="11.10.7.3",
                condition_checked="no_expected_credit",
            )
        )

    if not results:
        results.append(
            ValidityCheckResult(
                is_valid=True,
                reason="No invalid conditions found for 13.6",
                rule_section="11.10.7.3",
                condition_checked="all_checks_passed",
            )
        )

    return results


# Registry of validity checkers per condition
VALIDITY_CHECKERS: dict[DisputeCondition, type] = {}


def check_dispute_validity(case: DisputeCase) -> list[ValidityCheckResult]:
    """Run all applicable validity checks for a dispute case.

    Returns a list of validity check results. If any result has is_valid=False,
    the dispute is considered invalid under that condition.
    """
    if case.condition is None:
        return [
            ValidityCheckResult(
                is_valid=False,
                reason="No dispute condition assigned",
                rule_section="11.6",
                condition_checked="condition_assignment",
            )
        ]

    checker_map = {
        DisputeCondition.EMV_COUNTERFEIT_FRAUD: check_condition_10_1_validity,
        DisputeCondition.EMV_NON_COUNTERFEIT_FRAUD: check_condition_10_2_validity,
        DisputeCondition.OTHER_FRAUD_CARD_PRESENT: check_condition_10_3_validity,
        DisputeCondition.OTHER_FRAUD_CARD_ABSENT: check_condition_10_4_validity,
        DisputeCondition.CARD_RECOVERY_BULLETIN: check_condition_11_1_validity,
        DisputeCondition.DECLINED_AUTHORIZATION: check_condition_11_2_validity,
        DisputeCondition.NO_AUTHORIZATION: check_condition_11_3_validity,
        DisputeCondition.INCORRECT_AMOUNT: check_condition_12_5_validity,
        DisputeCondition.DUPLICATE_PROCESSING: check_condition_12_6_validity,
        DisputeCondition.MERCHANDISE_NOT_RECEIVED: check_condition_13_1_validity,
        DisputeCondition.CANCELLED_RECURRING: check_condition_13_2_validity,
        DisputeCondition.CREDIT_NOT_PROCESSED: check_condition_13_6_validity,
    }

    checker = checker_map.get(case.condition)
    if checker is None:
        return [
            ValidityCheckResult(
                is_valid=True,
                reason=f"No specific validity checker for {case.condition.value}; default valid",
                rule_section="11.6",
                condition_checked="default_pass",
            )
        ]

    return checker(case)


def convert_to_rule_evaluation(result: ValidityCheckResult) -> RuleEvaluationResult:
    """Convert a validity check result to a rule evaluation result for recording."""
    return RuleEvaluationResult(
        rule_id=f"validity_{result.condition_checked}",
        rule_section=result.rule_section,
        rule_description=result.reason,
        is_satisfied=result.is_valid,
        details=result.reason,
        evaluated_at=datetime.utcnow(),
    )
