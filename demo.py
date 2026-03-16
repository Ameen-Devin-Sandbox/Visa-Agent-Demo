"""Demo script showing the Visa Disputes Processing Brain in action.

This script demonstrates the end-to-end flow of dispute processing
across all four dispute categories.
"""

import asyncio
import logging
from datetime import date

from src.models.dispute import (
    CardholderInfo,
    DisputeCase,
    DisputeEvidence,
    TransactionDetails,
)
from src.models.enums import (
    FraudTypeCode,
    Region,
    TransactionEnvironment,
)
from src.orchestrator.brain import DisputeBrain
from src.queue.task_queue import DisputeTaskQueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("demo")


def create_fraud_dispute() -> DisputeCase:
    """Create a sample fraud dispute (Category 10.4 - Card-Absent Fraud)."""
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-FRAUD-001",
            transaction_date=date(2026, 2, 15),
            processing_date=date(2026, 2, 16),
            amount=1250.00,
            currency="USD",
            merchant_name="SuspiciousStore.com",
            merchant_category_code="5411",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="422222",
            environment=TransactionEnvironment.ECOMMERCE,
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Jane Doe",
            partial_payment_credential="****1234",
            contact_email="jane@example.com",
            cardholder_statement="I did not authorize this transaction. I have never shopped at this store.",
            signed_letter_provided=True,
        ),
        fraud_type_code=FraudTypeCode.ACCOUNT_TAKEOVER,
        issuer_certification="Issuer certifies cardholder denies authorization of the transaction",
        evidence=[
            DisputeEvidence(
                description="Cardholder signed letter denying transaction",
                evidence_type="cardholder_letter",
                provided_by="issuer",
            ),
        ],
    )


def create_authorization_dispute() -> DisputeCase:
    """Create a sample authorization dispute (Category 11.2 - Declined Auth)."""
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-AUTH-001",
            transaction_date=date(2026, 2, 20),
            processing_date=date(2026, 2, 21),
            amount=500.00,
            currency="USD",
            merchant_name="RetailStore Inc",
            merchant_category_code="5311",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="433333",
            environment=TransactionEnvironment.CARD_PRESENT,
            authorization_response_code="05",  # Declined
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="John Smith",
            partial_payment_credential="****5678",
            cardholder_statement="My card was declined but I was still charged for this transaction.",
        ),
        evidence=[
            DisputeEvidence(
                description="Authorization decline response code 05 recorded",
                evidence_type="authorization_record",
                provided_by="issuer",
            ),
        ],
    )


def create_processing_error_dispute() -> DisputeCase:
    """Create a sample processing error dispute (Category 12.5 - Incorrect Amount)."""
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-PROC-001",
            transaction_date=date(2026, 2, 25),
            processing_date=date(2026, 2, 26),
            amount=350.00,
            currency="USD",
            merchant_name="CoffeeShop",
            merchant_category_code="5812",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="444444",
            environment=TransactionEnvironment.CARD_PRESENT,
            authorization_code="ABC123",
            authorization_response_code="00",
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Alice Johnson",
            partial_payment_credential="****9012",
            cardholder_statement="I was charged $350 but the receipt shows $35. This is an incorrect amount.",
        ),
        dispute_amount=35.00,
        evidence=[
            DisputeEvidence(
                description="Receipt showing correct amount of $35.00",
                evidence_type="receipt",
                provided_by="issuer",
            ),
        ],
    )


def create_consumer_dispute() -> DisputeCase:
    """Create a sample consumer dispute (Category 13.1 - Merchandise Not Received)."""
    return DisputeCase(
        transaction=TransactionDetails(
            transaction_id="TXN-CONS-001",
            transaction_date=date(2026, 1, 15),
            processing_date=date(2026, 1, 16),
            amount=899.99,
            currency="USD",
            merchant_name="OnlineGadgets.com",
            merchant_category_code="5732",
            merchant_country="US",
            acquirer_bin="411111",
            issuer_bin="455555",
            environment=TransactionEnvironment.ECOMMERCE,
            authorization_code="XYZ789",
            authorization_response_code="00",
            region=Region.US,
        ),
        cardholder=CardholderInfo(
            cardholder_name="Bob Williams",
            partial_payment_credential="****3456",
            cardholder_statement="I ordered a laptop but it was never received. Merchant is not responding.",
            signed_letter_provided=True,
        ),
        evidence=[
            DisputeEvidence(
                description="Order confirmation showing expected delivery date of Jan 25, 2026",
                evidence_type="order_confirmation",
                provided_by="issuer",
            ),
            DisputeEvidence(
                description="Evidence of multiple contact attempts with merchant",
                evidence_type="communication_record",
                provided_by="issuer",
            ),
        ],
    )


def print_case_result(case: DisputeCase, title: str) -> None:
    """Pretty-print the results of a processed dispute case."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print(f"  Case ID:      {case.case_id}")
    print(f"  Category:     {case.category.value if case.category else 'N/A'}")
    print(f"  Condition:    {case.condition.value if case.condition else 'N/A'}")
    print(f"  Stage:        {case.stage.value}")
    print(f"  Agent:        {case.assigned_agent}")

    if case.decision:
        print(f"\n  Resolution:   {case.decision.resolution.value}")
        print(f"  Confidence:   {case.decision.confidence_score:.2f}")
        print(f"  Human Review: {case.decision.requires_human_review}")
        print(f"  Rationale:    {case.decision.rationale[:120]}...")

    print(f"\n  Rule Evaluations: {len(case.rule_evaluations)}")
    for eval_result in case.rule_evaluations:
        status = "PASS" if eval_result.is_satisfied else "FAIL"
        print(f"    [{status}] {eval_result.rule_id} (Section {eval_result.rule_section})")

    print(f"\n  Processing Notes ({len(case.processing_notes)}):")
    for note in case.processing_notes[:5]:
        print(f"    - {note}")

    print(f"\n  Stage History ({len(case.stage_history)}):")
    for entry in case.stage_history:
        print(f"    {entry['from_stage']} -> {entry['to_stage']}: {entry.get('note', '')}")

    print("-" * 80)


async def run_demo() -> None:
    """Run the full demonstration of the Disputes Processing Brain."""
    print("\n" + "#" * 80)
    print("#   VISA DISPUTES PROCESSING BRAIN - DEMO")
    print("#" * 80)

    # Initialize the system
    task_queue = DisputeTaskQueue()
    brain = DisputeBrain(task_queue)

    # Demo 1: Fraud Dispute (Category 10)
    print("\n>>> Demo 1: Fraud Dispute - Card-Absent Environment")
    fraud_case = create_fraud_dispute()
    processed_fraud = await brain.process_single(fraud_case)
    print_case_result(processed_fraud, "FRAUD DISPUTE (Category 10.4)")

    # Demo 2: Authorization Dispute (Category 11)
    print("\n>>> Demo 2: Authorization Dispute - Declined Authorization")
    auth_case = create_authorization_dispute()
    processed_auth = await brain.process_single(auth_case)
    print_case_result(processed_auth, "AUTHORIZATION DISPUTE (Category 11.2)")

    # Demo 3: Processing Error (Category 12)
    print("\n>>> Demo 3: Processing Error - Incorrect Amount")
    proc_case = create_processing_error_dispute()
    processed_proc = await brain.process_single(proc_case)
    print_case_result(processed_proc, "PROCESSING ERROR (Category 12.5)")

    # Demo 4: Consumer Dispute (Category 13)
    print("\n>>> Demo 4: Consumer Dispute - Merchandise Not Received")
    consumer_case = create_consumer_dispute()
    processed_consumer = await brain.process_single(consumer_case)
    print_case_result(processed_consumer, "CONSUMER DISPUTE (Category 13.1)")

    # Demo 5: Pre-Arbitration Escalation
    print("\n>>> Demo 5: Pre-Arbitration Escalation on Fraud Case")
    # Acquirer submits compelling evidence
    processed_fraud.add_evidence(
        DisputeEvidence(
            description="Two prior undisputed transactions from same IP address and device",
            evidence_type="previous_undisputed_transactions",
            provided_by="acquirer",
            is_compelling_evidence=True,
        )
    )
    escalated = await brain.escalate_to_pre_arbitration(processed_fraud.case_id)
    if escalated:
        print_case_result(escalated, "PRE-ARBITRATION ESCALATION")

    # Demo 6: Queue-based processing
    print("\n>>> Demo 6: Queue-Based Processing (3 disputes)")
    await brain.start()

    cases = [
        create_fraud_dispute(),
        create_authorization_dispute(),
        create_consumer_dispute(),
    ]
    for case in cases:
        await brain.submit_dispute(case)

    # Wait for processing
    await asyncio.sleep(2)

    print(f"\n  Queue Stats: {task_queue.get_stats()}")
    print(f"  Total Cases: {len(brain.get_all_cases())}")

    await brain.stop()

    # Summary
    print("\n" + "#" * 80)
    print("#   DEMO COMPLETE - Summary")
    print("#" * 80)
    print(f"  Total cases processed: {len(brain.get_all_cases())}")
    for case in brain.get_all_cases():
        summary = brain.get_case_summary(case.case_id)
        if summary:
            print(
                f"    Case {summary['case_id'][:8]}... | "
                f"Category: {summary['category'] or 'N/A':4s} | "
                f"Stage: {summary['stage']:20s} | "
                f"Resolution: {summary['resolution'] or 'pending'}"
            )
    print()


if __name__ == "__main__":
    asyncio.run(run_demo())
