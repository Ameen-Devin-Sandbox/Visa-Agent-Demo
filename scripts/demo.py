"""Demo script — runs the dispute processing system end-to-end.

Demonstrates the rule engine, orchestrator, and agent pipeline
using a mock LLM so no API keys are needed.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.agents.orchestrator import Orchestrator
from src.config import AppConfig
from src.llm.base import LLMMessage, LLMProvider, LLMResponse
from src.models.dispute import Dispute, DocumentEvidence, Party, TransactionDetail
from src.models.enums import (
    DisputeCategory,
    DisputeCondition,
    DisputeStatus,
    FraudType,
    PartyRole,
    Region,
    TransactionEnvironment,
)
from src.queue.memory import InMemoryQueue
from src.rules.engine import RuleEngine
from src.rules.registry import (
    ALL_CONDITIONS,
    CONDITIONS_BY_CATEGORY,
    get_compelling_evidence_for_condition,
    get_condition_rule,
)

console = Console()
engine = RuleEngine()


# ── Mock LLM ────────────────────────────────────────────────────────────────

class DemoLLM(LLMProvider):
    """Mock LLM that returns plausible responses for demo purposes."""

    async def complete(self, messages, temperature=0.1, max_tokens=4096):
        prompt = messages[-1].content if messages else ""

        if "determine" in prompt.lower() or "condition" in prompt.lower():
            content = (
                "Based on the transaction facts (card-absent e-commerce environment, "
                "cardholder denies participation, fraud reported to Visa), condition 10.4 "
                "(Other Fraud - Card-Absent Environment) is the most appropriate. "
                "Confidence: 95%. The ECI indicator of 7 (non-authenticated) means this is "
                "not protected by 3DS, so the dispute is valid."
            )
        elif "invalid" in prompt.lower():
            content = (
                "After reviewing all conditions requiring manual evaluation:\n"
                "- No delayed charge indicators present\n"
                "- Transaction is not Visa Commercial Choice Omni\n"
                "- No crypto/NFT involvement\n"
                "Conclusion: None of the manually-evaluated invalid conditions are triggered."
            )
        elif "compelling" in prompt.lower():
            content = (
                "For this e-commerce transaction, the Acquirer could potentially provide:\n"
                "- CE #3: Delivery to AVS-matched address (if applicable)\n"
                "- CE #4: Digital goods download evidence\n"
                "- CE #10: Matching account/device/IP data from prior undisputed transactions\n"
                "The CE case strength depends on what data the Acquirer has retained."
            )
        elif "arbitration" in prompt.lower() or "pre-arb" in prompt.lower():
            content = (
                "The dispute/pre-arbitration cycle is not yet complete. "
                "Recommend waiting for the Acquirer's pre-arbitration attempt before "
                "considering arbitration. If the Acquirer provides compelling evidence, "
                "the Issuer must evaluate it and either accept or provide counter-evidence."
            )
        else:
            content = "Analysis complete. Proceeding with the recommended action based on Visa Rules."

        return LLMResponse(content=content, model="demo-mock", usage={"input_tokens": 100, "output_tokens": 80})

    async def complete_with_tools(self, messages, tools, temperature=0.1, max_tokens=4096):
        return await self.complete(messages, temperature, max_tokens)


# ── Sample Disputes ─────────────────────────────────────────────────────────

DISPUTES = [
    # 1. Card-absent fraud (should be eligible)
    Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-00471",
            acquirer_reference_number="ARN-74927482001",
            transaction_date=date.today() - timedelta(days=45),
            processing_date=date.today() - timedelta(days=44),
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
                description="Cardholder certifies they did not authorize this transaction",
                provided_by=PartyRole.ISSUER,
                provided_date=date.today(),
            ),
        ],
    ),
    # 2. 3DS-authenticated fraud (should be INVALID — Secure E-Commerce with ECI 5 + CAVV)
    Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-00472",
            transaction_date=date.today() - timedelta(days=20),
            processing_date=date.today() - timedelta(days=19),
            amount=Decimal("1250.00"),
            currency="USD",
            merchant_name="LuxuryGoods.com",
            merchant_category_code="5944",
            merchant_country="US",
            environment=TransactionEnvironment.ECOMMERCE,
            eci_indicator="5",
            cavv_present=True,
            three_ds_authenticated=True,
            fraud_type_reported=FraudType.CARD_ABSENT,
        ),
        category=DisputeCategory.FRAUD,
        issuer=Party(role=PartyRole.ISSUER, name="Bank of America", institution_id="BOA001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Adyen", institution_id="ADYEN001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="John Smith"),
        merchant=Party(role=PartyRole.MERCHANT, name="LuxuryGoods.com"),
        fraud_reported_to_visa=True,
        fraud_type=FraudType.CARD_ABSENT,
        cardholder_financial_loss=True,
    ),
    # 3. Consumer not received (should be eligible, but with wait period warning)
    Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-00473",
            transaction_date=date.today() - timedelta(days=10),
            processing_date=date.today() - timedelta(days=9),
            amount=Decimal("89.99"),
            currency="USD",
            merchant_name="GadgetStore Inc.",
            merchant_category_code="5732",
            merchant_country="US",
            environment=TransactionEnvironment.ECOMMERCE,
        ),
        category=DisputeCategory.CONSUMER_DISPUTES,
        issuer=Party(role=PartyRole.ISSUER, name="Wells Fargo", institution_id="WF001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Square", institution_id="SQ001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Alice Johnson"),
        merchant=Party(role=PartyRole.MERCHANT, name="GadgetStore Inc."),
        cardholder_financial_loss=True,
        cardholder_attempted_resolution=True,
    ),
    # 4. Expired time limit (should be INELIGIBLE)
    Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2024-09912",
            transaction_date=date.today() - timedelta(days=200),
            processing_date=date.today() - timedelta(days=199),
            amount=Decimal("500.00"),
            currency="USD",
            merchant_name="OldMerchant LLC",
            merchant_category_code="5411",
            merchant_country="US",
            environment=TransactionEnvironment.CARD_ABSENT,
            fraud_type_reported=FraudType.CARD_ABSENT,
        ),
        category=DisputeCategory.FRAUD,
        issuer=Party(role=PartyRole.ISSUER, name="Citi", institution_id="CITI001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="PayPal", institution_id="PP001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Bob Williams"),
        merchant=Party(role=PartyRole.MERCHANT, name="OldMerchant LLC"),
        fraud_reported_to_visa=True,
        fraud_type=FraudType.CARD_ABSENT,
        cardholder_financial_loss=True,
    ),
    # 5. Mobile Push Payment fraud (should be INVALID)
    Dispute(
        transaction=TransactionDetail(
            transaction_id="TXN-2025-00474",
            transaction_date=date.today() - timedelta(days=30),
            processing_date=date.today() - timedelta(days=29),
            amount=Decimal("75.00"),
            currency="USD",
            merchant_name="CoffeeShop",
            merchant_category_code="5814",
            merchant_country="US",
            environment=TransactionEnvironment.CARD_PRESENT,
            is_mobile_push_payment=True,
        ),
        category=DisputeCategory.FRAUD,
        issuer=Party(role=PartyRole.ISSUER, name="US Bank", institution_id="USB001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Toast", institution_id="TOAST001", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Carol Davis"),
        merchant=Party(role=PartyRole.MERCHANT, name="CoffeeShop"),
        fraud_reported_to_visa=True,
        cardholder_financial_loss=True,
    ),
]


# ── Part 1: Rule Engine Demo ────────────────────────────────────────────────

def demo_rule_registry():
    """Show the full registry of encoded rules."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]PART 1: ENCODED VISA DISPUTE RULES[/bold cyan]\n"
        "All 23 conditions from Chapter 11 of the Visa Core Rules",
        border_style="cyan",
    ))

    table = Table(title="Dispute Conditions Registry", show_lines=True)
    table.add_column("Code", style="bold yellow", width=6)
    table.add_column("Name", style="white", width=40)
    table.add_column("Time Limit", style="green", width=12)
    table.add_column("Invalid Conditions", style="red", justify="center", width=8)
    table.add_column("Docs Required", justify="center", width=6)
    table.add_column("Has CE", justify="center", width=6)

    for cat_name, cat_enum in [
        ("FRAUD", DisputeCategory.FRAUD),
        ("AUTH", DisputeCategory.AUTHORIZATION),
        ("PROC ERRORS", DisputeCategory.PROCESSING_ERRORS),
        ("CONSUMER", DisputeCategory.CONSUMER_DISPUTES),
    ]:
        rules = CONDITIONS_BY_CATEGORY[cat_enum]
        for i, rule in enumerate(rules):
            ce = get_compelling_evidence_for_condition(rule.condition)
            table.add_row(
                rule.condition.value,
                rule.name,
                f"{rule.time_limit.calendar_days}d" + (f" (max {rule.time_limit.max_calendar_days}d)" if rule.time_limit.max_calendar_days else ""),
                str(len(rule.invalid_conditions)),
                str(len(rule.documentation_requirements)),
                str(len(ce)) if ce else "-",
            )
        if cat_name != "CONSUMER":
            table.add_section()

    console.print(table)
    console.print(f"\n  [dim]Total conditions: {len(ALL_CONDITIONS)} | Total CE items: 16 (Table 11-6)[/dim]")


def demo_rule_evaluation():
    """Run the rule engine against sample disputes."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]PART 2: RULE ENGINE EVALUATION[/bold cyan]\n"
        "Processing 5 sample disputes through the rule engine",
        border_style="cyan",
    ))

    for i, dispute in enumerate(DISPUTES, 1):
        txn = dispute.transaction
        console.print(f"\n{'='*70}")
        console.print(f"[bold white]DISPUTE #{i}[/bold white]: {txn.transaction_id}")
        console.print(f"  Merchant: {txn.merchant_name} | Amount: ${txn.amount} {txn.currency}")
        console.print(f"  Date: {txn.transaction_date} | Environment: {txn.environment.value}")
        console.print(f"  Category: {dispute.category}")

        # Step 1: Determine condition
        console.print(f"\n  [bold]Step 1: Determine Dispute Condition[/bold]")
        candidates = engine.determine_condition(dispute)
        if candidates:
            for cond, conf, reason in candidates[:3]:
                bar = "=" * int(conf * 20)
                color = "green" if conf >= 0.8 else "yellow" if conf >= 0.5 else "red"
                console.print(f"    [{color}]{cond.value}[/{color}] {conf:.0%} {bar} {reason}")

            best_cond, best_conf, _ = candidates[0]
            dispute.condition = best_cond
        else:
            console.print("    [red]No condition matched[/red]")
            continue

        # Step 2: Check eligibility
        console.print(f"\n  [bold]Step 2: Evaluate Eligibility (Condition {dispute.condition.value})[/bold]")
        result = engine.evaluate_eligibility(dispute)

        if result.eligible:
            console.print(f"    [bold green]ELIGIBLE[/bold green]")
        else:
            console.print(f"    [bold red]INELIGIBLE[/bold red]")

        for reason in result.reasons:
            console.print(f"    [green]+[/green] {reason}")
        for block in result.blocking_reasons:
            console.print(f"    [red]X[/red] {block}")
        for warn in result.warnings:
            console.print(f"    [yellow]![/yellow] {warn}")

        if result.deadline:
            days_left = (result.deadline - date.today()).days
            color = "red" if days_left <= 7 else "yellow" if days_left <= 30 else "green"
            console.print(f"    Deadline: {result.deadline} ([{color}]{days_left} days remaining[/{color}])")

        # Step 3: Check invalid conditions
        console.print(f"\n  [bold]Step 3: Invalid Condition Check[/bold]")
        invalid_results = engine.check_invalid_conditions(dispute)
        triggered = [(inv, expl) for inv, t, expl in invalid_results if t]
        clear = [(inv, expl) for inv, t, expl in invalid_results if not t]

        if triggered:
            for inv, expl in triggered:
                console.print(f"    [red]TRIGGERED[/red] {inv.condition_id}: {inv.description}")
        console.print(f"    [dim]Checked {len(invalid_results)} conditions: {len(triggered)} triggered, {len(clear)} clear[/dim]")

        # Step 4: Required documentation
        console.print(f"\n  [bold]Step 4: Documentation Requirements[/bold]")
        docs = engine.get_required_documentation(dispute)
        for doc in docs:
            color = "red" if doc.startswith("[REQUIRED]") else "dim"
            console.print(f"    [{color}]{doc}[/{color}]")
        if not docs:
            console.print(f"    [dim]No specific documentation requirements[/dim]")

        # Step 5: Compelling Evidence
        ce_options = engine.get_compelling_evidence_options(dispute)
        if ce_options:
            console.print(f"\n  [bold]Step 5: Compelling Evidence Options ({len(ce_options)} types)[/bold]")
            for ce in ce_options[:5]:
                console.print(f"    [cyan]{ce}[/cyan]")
            if len(ce_options) > 5:
                console.print(f"    [dim]... and {len(ce_options) - 5} more[/dim]")

        # Step 6: Deadlines
        if dispute.condition:
            console.print(f"\n  [bold]Step 6: Deadlines[/bold]")
            deadlines = engine.calculate_deadlines(dispute)
            console.print(f"    Filing deadline:    {deadlines.dispute_deadline}")
            if deadlines.wait_until:
                console.print(f"    Wait until:         {deadlines.wait_until}")
            if deadlines.max_absolute_deadline:
                console.print(f"    Absolute max:       {deadlines.max_absolute_deadline}")
            console.print(f"    Rule: {deadlines.description}")


# ── Part 3: Orchestrator Pipeline Demo ───────────────────────────────────────

async def demo_orchestrator_pipeline():
    """Run disputes through the full orchestrator pipeline."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]PART 3: ORCHESTRATOR PIPELINE[/bold cyan]\n"
        "Running Dispute #1 through the full agent pipeline",
        border_style="cyan",
    ))

    config = AppConfig()
    queue = InMemoryQueue()
    llm = DemoLLM()
    orchestrator = Orchestrator(config=config, queue=queue, llm=llm)

    # Submit the first dispute (eligible fraud case)
    dispute = DISPUTES[0]
    await orchestrator.submit_dispute(dispute)
    console.print(f"\n  Submitted dispute {dispute.dispute_id}")
    console.print(f"  Merchant: {dispute.transaction.merchant_name}")
    console.print(f"  Amount: ${dispute.transaction.amount}")

    # Process tasks
    console.print(f"\n  [bold]Processing pipeline...[/bold]\n")
    iteration = 0
    while iteration < 15:
        result = await orchestrator.process_next()
        if result is None:
            pending = await queue.get_pending_count()
            if pending == 0:
                break
            await asyncio.sleep(0.01)
            continue

        iteration += 1
        status_icon = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
        console.print(f"  [{iteration:2d}] {status_icon} {result.decision}")

        # Show key details
        if result.data:
            if "condition" in result.data:
                console.print(f"       Condition: {result.data['condition']} (confidence: {result.data.get('confidence', 'N/A')})")
            if "eligible" in result.data:
                elig = result.data["eligible"]
                console.print(f"       Eligible: {'Yes' if elig else 'No'}")
                if result.data.get("deadline"):
                    console.print(f"       Deadline: {result.data['deadline']}")
                if result.data.get("blocking_reasons"):
                    for br in result.data["blocking_reasons"]:
                        console.print(f"       [red]Block: {br}[/red]")
            if "amount_rule" in result.data:
                console.print(f"       Amount rule: {result.data['amount_rule']}")

        for warn in result.warnings:
            console.print(f"       [yellow]Warning: {warn}[/yellow]")

    # Final status
    status = await orchestrator.get_dispute_status(str(dispute.dispute_id))
    console.print(f"\n  [bold]Final Status:[/bold]")
    console.print(f"    Status:    {status['status']}")
    console.print(f"    Phase:     {status['phase']}")
    console.print(f"    Category:  {status['category']}")
    console.print(f"    Condition: {status['condition']}")
    console.print(f"    Tasks run: {len(status['tasks'])}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold white]VISA DISPUTES PROCESSING AGENT[/bold white]\n"
        "[dim]Autonomous dispute processor based on Visa Core Rules (Oct 2025)[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))

    demo_rule_registry()
    demo_rule_evaluation()
    asyncio.run(demo_orchestrator_pipeline())

    console.print(f"\n{'='*70}")
    console.print("[bold green]Demo complete.[/bold green]\n")


if __name__ == "__main__":
    main()
