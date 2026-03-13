"""Entry point for the Visa Disputes Processing Agent."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal

import structlog

from src.agents.orchestrator import Orchestrator
from src.config import AppConfig
from src.llm.factory import create_llm_provider
from src.models.dispute import Dispute, Party, TransactionDetail
from src.models.enums import (
    DisputeCategory,
    FraudType,
    PartyRole,
    Region,
    TransactionEnvironment,
)
from src.queue.memory import InMemoryQueue


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def create_sample_dispute_fraud_card_absent() -> Dispute:
    """Create a sample fraud (card-absent) dispute for demo purposes."""
    return Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-001",
            acquirer_reference_number="ARN-74927482001",
            transaction_date=date(2025, 1, 15),
            processing_date=date(2025, 1, 16),
            amount=Decimal("250.00"),
            currency="USD",
            merchant_name="OnlineShop.com",
            merchant_category_code="5411",
            merchant_country="US",
            environment=TransactionEnvironment.ECOMMERCE,
            eci_indicator="7",  # Non-authenticated
            cavv_present=False,
            three_ds_authenticated=False,
            fraud_type_reported=FraudType.CARD_ABSENT,
        ),
        category=DisputeCategory.FRAUD,
        issuer=Party(role=PartyRole.ISSUER, name="Chase Bank", institution_id="CHASE001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Stripe", institution_id="STRIPE001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Jane Doe"),
        merchant=Party(role=PartyRole.MERCHANT, name="OnlineShop.com"),
        fraud_reported_to_visa=True,
        fraud_type=FraudType.CARD_ABSENT,
        cardholder_financial_loss=True,
        disputes_on_account_last_120_days=2,
    )


def create_sample_dispute_not_received() -> Dispute:
    """Create a sample consumer (not received) dispute for demo purposes."""
    return Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-002",
            transaction_date=date(2025, 2, 1),
            processing_date=date(2025, 2, 2),
            amount=Decimal("89.99"),
            currency="USD",
            merchant_name="GadgetStore Inc.",
            merchant_category_code="5732",
            merchant_country="US",
            environment=TransactionEnvironment.ECOMMERCE,
        ),
        category=DisputeCategory.CONSUMER_DISPUTES,
        issuer=Party(role=PartyRole.ISSUER, name="Bank of America", institution_id="BOA001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Square", institution_id="SQUARE001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="John Smith"),
        merchant=Party(role=PartyRole.MERCHANT, name="GadgetStore Inc."),
        cardholder_financial_loss=True,
        cardholder_attempted_resolution=True,
    )


async def run_demo(config: AppConfig) -> None:
    """Run a demo of the dispute processing system."""
    log = structlog.get_logger()
    log.info("Starting Visa Disputes Processing Agent")

    # Initialize components
    queue = InMemoryQueue()
    llm = create_llm_provider(config.llm)
    orchestrator = Orchestrator(config=config, queue=queue, llm=llm)

    # Submit sample disputes
    dispute1 = create_sample_dispute_fraud_card_absent()
    dispute2 = create_sample_dispute_not_received()

    log.info("Submitting sample disputes")
    await orchestrator.submit_dispute(dispute1)
    await orchestrator.submit_dispute(dispute2)

    log.info(f"Dispute 1 (Fraud/Card-Absent): {dispute1.dispute_id}")
    log.info(f"Dispute 2 (Consumer/Not Received): {dispute2.dispute_id}")

    # Process all tasks
    log.info("Processing dispute tasks...")
    max_iterations = 20
    iteration = 0

    while iteration < max_iterations:
        result = await orchestrator.process_next()
        if result is None:
            pending = await queue.get_pending_count()
            if pending == 0:
                log.info("All tasks processed")
                break
            await asyncio.sleep(0.1)
            continue

        iteration += 1
        log.info(
            f"[{iteration}] Decision: {result.decision}",
            success=result.success,
            reasoning=result.reasoning[:200] + "..." if len(result.reasoning) > 200 else result.reasoning,
        )

    # Print final status
    print("\n" + "=" * 80)
    print("FINAL DISPUTE STATUS")
    print("=" * 80)

    for dispute in [dispute1, dispute2]:
        status = await orchestrator.get_dispute_status(str(dispute.dispute_id))
        print(f"\nDispute: {status['dispute_id']}")
        print(f"  Status: {status['status']}")
        print(f"  Phase: {status['phase']}")
        print(f"  Category: {status['category']}")
        print(f"  Condition: {status['condition']}")
        print(f"  Tasks: {len(status['tasks'])}")
        for task_info in status["tasks"]:
            result_info = task_info.get("result")
            decision = result_info.decision if result_info else "N/A"
            print(f"    [{task_info['status']}] {task_info['type']}: {decision}")


def main() -> None:
    """Main entry point."""
    config = AppConfig()
    setup_logging(config.log_level)
    asyncio.run(run_demo(config))


if __name__ == "__main__":
    main()
