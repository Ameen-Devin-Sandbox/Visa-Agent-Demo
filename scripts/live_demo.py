"""Live demo — runs disputes through the real LLM-powered pipeline.

Uses the OpenAI API key from .env to power agent reasoning.
Run with: python -m scripts.live_demo
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agents.orchestrator import Orchestrator
from src.config import AppConfig
from src.llm.factory import create_llm_provider
from src.models.dispute import Dispute, DocumentEvidence, Party, TransactionDetail
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    DisputePhase,
    DisputeStatus,
    FraudType,
    PartyRole,
    Region,
    TransactionEnvironment,
)
from src.queue.memory import InMemoryQueue

console = Console(width=110)


def setup_logging():
    logging.basicConfig(level=logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ── Scenarios ────────────────────────────────────────────────────────────────

def make_scenarios() -> list[tuple[str, Dispute]]:
    """Build scenarios with fresh dates relative to today."""
    today = date.today()
    return [
        (
            "E-commerce fraud: cardholder denies $349 purchase at ShadyElectronics.com (non-3DS)",
            Dispute(
                transaction=TransactionDetail(
                    transaction_id="TXN-LIVE-001",
                    acquirer_reference_number="ARN-74927482001",
                    transaction_date=today - timedelta(days=45),
                    processing_date=today - timedelta(days=44),
                    amount=Decimal("349.99"),
                    currency="USD",
                    merchant_name="ShadyElectronics.com",
                    merchant_category_code="5732",
                    merchant_country="US",
                    environment=TransactionEnvironment.ECOMMERCE,
                    eci_indicator="7",
                    cavv_present=False,
                    three_ds_authenticated=False,
                    fraud_type_reported=FraudType.CARD_ABSENT,
                ),
                category=DisputeCategory.FRAUD,
                issuer=Party(role=PartyRole.ISSUER, name="Chase Bank", institution_id="CHASE001", region=Region.US),
                acquirer=Party(role=PartyRole.ACQUIRER, name="Stripe Inc.", institution_id="STRIPE001", region=Region.US),
                cardholder=Party(role=PartyRole.CARDHOLDER, name="Jane Doe"),
                merchant=Party(role=PartyRole.MERCHANT, name="ShadyElectronics.com"),
                fraud_reported_to_visa=True,
                fraud_type=FraudType.CARD_ABSENT,
                cardholder_financial_loss=True,
                disputes_on_account_last_120_days=2,
                evidence=[
                    DocumentEvidence(
                        document_type="cardholder_certification",
                        description="Cardholder certifies she did not authorize this transaction",
                        provided_by=PartyRole.ISSUER,
                        provided_date=today,
                    ),
                ],
            ),
        ),
        (
            "Cancelled recurring: StreamFlix keeps charging $14.99/mo after cancellation",
            Dispute(
                transaction=TransactionDetail(
                    transaction_id="TXN-LIVE-002",
                    transaction_date=today - timedelta(days=5),
                    processing_date=today - timedelta(days=4),
                    amount=Decimal("14.99"),
                    currency="USD",
                    merchant_name="StreamFlix",
                    merchant_category_code="4899",
                    merchant_country="US",
                    environment=TransactionEnvironment.RECURRING,
                    is_recurring=True,
                ),
                category=DisputeCategory.CONSUMER_DISPUTES,
                condition=DisputeCondition.CONSUMER_CANCELLED_RECURRING,
                issuer=Party(role=PartyRole.ISSUER, name="Capital One", institution_id="COF001", region=Region.US),
                acquirer=Party(role=PartyRole.ACQUIRER, name="Worldpay", institution_id="WP001", region=Region.US),
                cardholder=Party(role=PartyRole.CARDHOLDER, name="Dave Miller"),
                merchant=Party(role=PartyRole.MERCHANT, name="StreamFlix"),
                cardholder_financial_loss=True,
                cardholder_attempted_resolution=True,
                evidence=[
                    DocumentEvidence(
                        document_type="cancellation_confirmation",
                        description="Email from StreamFlix confirming subscription cancelled on 2026-01-10",
                        provided_by=PartyRole.CARDHOLDER,
                        provided_date=today,
                    ),
                    DocumentEvidence(
                        document_type="cardholder_statement",
                        description="Cardholder statement: cancelled service, charge is unauthorized",
                        provided_by=PartyRole.ISSUER,
                        provided_date=today,
                    ),
                ],
            ),
        ),
        (
            "Duplicate charge: RetailStore charged $250 twice for one purchase",
            Dispute(
                transaction=TransactionDetail(
                    transaction_id="TXN-LIVE-003",
                    transaction_date=today - timedelta(days=12),
                    processing_date=today - timedelta(days=11),
                    amount=Decimal("250.00"),
                    currency="USD",
                    merchant_name="RetailStore",
                    merchant_category_code="5411",
                    merchant_country="US",
                    environment=TransactionEnvironment.CARD_PRESENT,
                ),
                category=DisputeCategory.PROCESSING_ERRORS,
                condition=DisputeCondition.PROC_DUPLICATE,
                issuer=Party(role=PartyRole.ISSUER, name="US Bank", institution_id="USB001", region=Region.US),
                acquirer=Party(role=PartyRole.ACQUIRER, name="Fiserv", institution_id="FIS001", region=Region.US),
                cardholder=Party(role=PartyRole.CARDHOLDER, name="Carol Davis"),
                merchant=Party(role=PartyRole.MERCHANT, name="RetailStore"),
                cardholder_financial_loss=True,
                evidence=[
                    DocumentEvidence(
                        document_type="cardholder_statement",
                        description="Cardholder statement identifying the duplicate charge",
                        provided_by=PartyRole.ISSUER,
                        provided_date=today,
                    ),
                    DocumentEvidence(
                        document_type="proof_of_other_payment",
                        description="Documentation of both transactions showing identical amounts and merchant",
                        provided_by=PartyRole.ISSUER,
                        provided_date=today,
                    ),
                ],
            ),
        ),
        (
            "Expired time limit: $500 fraud claim from 200 days ago (should be REJECTED)",
            Dispute(
                transaction=TransactionDetail(
                    transaction_id="TXN-LIVE-004",
                    transaction_date=today - timedelta(days=200),
                    processing_date=today - timedelta(days=199),
                    amount=Decimal("500.00"),
                    currency="USD",
                    merchant_name="OldMerchant LLC",
                    merchant_category_code="5411",
                    merchant_country="US",
                    environment=TransactionEnvironment.CARD_ABSENT,
                    fraud_type_reported=FraudType.CARD_ABSENT,
                ),
                category=DisputeCategory.FRAUD,
                condition=DisputeCondition.FRAUD_CARD_ABSENT,
                issuer=Party(role=PartyRole.ISSUER, name="Citi", institution_id="CITI001", region=Region.US),
                acquirer=Party(role=PartyRole.ACQUIRER, name="PayPal", institution_id="PP001", region=Region.US),
                cardholder=Party(role=PartyRole.CARDHOLDER, name="Bob Williams"),
                merchant=Party(role=PartyRole.MERCHANT, name="OldMerchant LLC"),
                fraud_reported_to_visa=True,
                fraud_type=FraudType.CARD_ABSENT,
                cardholder_financial_loss=True,
            ),
        ),
        (
            "Merchandise not received: $89.99 gadget ordered 30 days ago, never delivered",
            Dispute(
                transaction=TransactionDetail(
                    transaction_id="TXN-LIVE-005",
                    transaction_date=today - timedelta(days=30),
                    processing_date=today - timedelta(days=29),
                    amount=Decimal("89.99"),
                    currency="USD",
                    merchant_name="GadgetStore Inc.",
                    merchant_category_code="5732",
                    merchant_country="US",
                    environment=TransactionEnvironment.ECOMMERCE,
                ),
                category=DisputeCategory.CONSUMER_DISPUTES,
                condition=DisputeCondition.CONSUMER_NOT_RECEIVED,
                issuer=Party(role=PartyRole.ISSUER, name="Wells Fargo", institution_id="WF001", region=Region.US),
                acquirer=Party(role=PartyRole.ACQUIRER, name="Square", institution_id="SQ001", region=Region.US),
                cardholder=Party(role=PartyRole.CARDHOLDER, name="Alice Johnson"),
                merchant=Party(role=PartyRole.MERCHANT, name="GadgetStore Inc."),
                cardholder_financial_loss=True,
                cardholder_attempted_resolution=True,
                evidence=[
                    DocumentEvidence(
                        document_type="cardholder_certification",
                        description="Cardholder certifies merchandise was not received",
                        provided_by=PartyRole.ISSUER,
                        provided_date=today,
                    ),
                    DocumentEvidence(
                        document_type="merchant_contact",
                        description="Email thread showing cardholder contacted merchant on 3 occasions with no resolution",
                        provided_by=PartyRole.CARDHOLDER,
                        provided_date=today,
                    ),
                    DocumentEvidence(
                        document_type="expected_delivery_date",
                        description="Order confirmation showing expected delivery date was 15 days ago",
                        provided_by=PartyRole.CARDHOLDER,
                        provided_date=today,
                    ),
                    DocumentEvidence(
                        document_type="tracking_info",
                        description="USPS tracking shows package stuck in transit for 20 days",
                        provided_by=PartyRole.CARDHOLDER,
                        provided_date=today,
                    ),
                ],
            ),
        ),
    ]


# ── Pipeline Runner ──────────────────────────────────────────────────────────

async def run_scenario(
    config: AppConfig, llm, label: str, dispute: Dispute, scenario_num: int
) -> dict:
    """Run a single dispute through the full pipeline and return results."""
    queue = InMemoryQueue()
    orchestrator = Orchestrator(config=config, queue=queue, llm=llm)

    console.print(f"\n{'='*110}")
    console.print(Panel(
        f"[bold]{label}[/bold]\n\n"
        f"Merchant: [yellow]{dispute.transaction.merchant_name}[/yellow] | "
        f"Amount: [green]${dispute.transaction.amount}[/green] | "
        f"Date: {dispute.transaction.transaction_date} | "
        f"Env: {dispute.transaction.environment.value}\n"
        f"Category: {dispute.category} | "
        f"Condition: {dispute.condition or 'auto-detect'} | "
        f"Issuer: {dispute.issuer.name} | Acquirer: {dispute.acquirer.name}",
        title=f"[bold white] SCENARIO {scenario_num} [/bold white]",
        border_style="bright_blue",
    ))

    await orchestrator.submit_dispute(dispute)

    results = []
    iteration = 0
    while iteration < 20:
        result = await orchestrator.process_next()
        if result is None:
            pending = await queue.get_pending_count()
            if pending == 0:
                break
            await asyncio.sleep(0.05)
            continue

        iteration += 1
        results.append(result)
        icon = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"

        console.print(f"\n  [bold]Task {iteration}[/bold]: {icon} [bold]{result.decision}[/bold]")

        # Print reasoning (truncated)
        reasoning = result.reasoning
        if len(reasoning) > 300:
            reasoning = reasoning[:300] + "..."
        console.print(f"  [dim]{reasoning}[/dim]")

        # Print key data
        if result.data:
            for key in ("condition", "confidence", "eligible", "deadline", "amount_rule", "blocking_reasons"):
                if key in result.data:
                    val = result.data[key]
                    if key == "eligible":
                        val = "[green]Yes[/green]" if val else "[red]No[/red]"
                    elif key == "blocking_reasons" and val:
                        for br in val:
                            console.print(f"  [red]BLOCKED: {br}[/red]")
                        continue
                    console.print(f"  {key}: {val}")

        if result.warnings:
            for w in result.warnings:
                console.print(f"  [yellow]Warning: {w}[/yellow]")

    # Final status
    status = await orchestrator.get_dispute_status(str(dispute.dispute_id))
    console.print(f"\n  [bold white on blue] RESULT [/bold white on blue]  "
                  f"status=[bold]{status['status']}[/bold]  "
                  f"phase=[bold]{status['phase']}[/bold]  "
                  f"condition=[bold]{status['condition']}[/bold]  "
                  f"tasks=[bold]{len(status['tasks'])}[/bold]")

    return status


async def main():
    setup_logging()

    console.print(Panel.fit(
        "[bold white]VISA DISPUTES PROCESSING AGENT — LIVE DEMO[/bold white]\n"
        "[dim]Powered by GPT-4o + Deterministic Rule Engine[/dim]\n"
        "[dim]Based on Visa Core Rules, Chapter 11 (Oct 2025)[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))

    config = AppConfig()
    llm = create_llm_provider(config.llm)
    console.print(f"\n  LLM Provider: [bold]{config.llm.provider}[/bold] / {config.llm.openai_model or config.llm.anthropic_model}")

    scenarios = make_scenarios()
    console.print(f"  Scenarios: [bold]{len(scenarios)}[/bold]\n")

    summary_rows = []
    for i, (label, dispute) in enumerate(scenarios, 1):
        try:
            status = await run_scenario(config, llm, label, dispute, i)
            summary_rows.append((
                str(i),
                dispute.transaction.merchant_name,
                f"${dispute.transaction.amount}",
                status["condition"] or "-",
                status["status"],
                str(len(status["tasks"])),
            ))
        except Exception as e:
            console.print(f"\n  [red]Scenario {i} failed: {e}[/red]")
            summary_rows.append((str(i), dispute.transaction.merchant_name, f"${dispute.transaction.amount}", "-", "ERROR", "0"))

    # Summary table
    console.print(f"\n{'='*110}")
    table = Table(title="Summary", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("Merchant", width=25)
    table.add_column("Amount", width=10)
    table.add_column("Condition", width=10)
    table.add_column("Result", width=20)
    table.add_column("Tasks", width=6)

    for row in summary_rows:
        status = row[4]
        style = "green" if status in ("eligible", "filed", "in_arbitration", "in_pre_arbitration") else "red" if status == "ineligible" else "yellow"
        table.add_row(row[0], row[1], row[2], row[3], f"[{style}]{status}[/{style}]", row[5])

    console.print(table)
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
