"""Interactive dispute processing CLI.

Run with: python -m scripts.interactive
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table

from src.agents.orchestrator import Orchestrator
from src.config import AppConfig
from src.llm.base import LLMProvider, LLMResponse
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
from src.rules.engine import RuleEngine
from src.rules.registry import (
    ALL_CONDITIONS,
    CONDITIONS_BY_CATEGORY,
    CONDITIONS_BY_CODE,
    get_compelling_evidence_for_condition,
    get_condition_rule,
)

console = Console(width=100)
engine = RuleEngine()


# ── Mock LLM ────────────────────────────────────────────────────────────────

class DemoLLM(LLMProvider):
    async def complete(self, messages, temperature=0.1, max_tokens=4096):
        prompt = messages[-1].content if messages else ""
        if "determine" in prompt.lower() or "condition" in prompt.lower():
            content = "Condition determined by rule engine heuristics. Proceeding with highest-confidence match."
        elif "compelling" in prompt.lower():
            content = "Compelling evidence analysis complete. See rule engine output for available CE types."
        elif "arbitration" in prompt.lower() or "pre-arb" in prompt.lower():
            content = "Pre-arbitration/arbitration stage reached. Evaluating options per Visa rules."
        else:
            content = "Analysis complete. Proceeding with recommended action per Visa Rules."
        return LLMResponse(content=content, model="demo-mock", usage={"input_tokens": 50, "output_tokens": 30})

    async def complete_with_tools(self, messages, tools, temperature=0.1, max_tokens=4096):
        return await self.complete(messages, temperature, max_tokens)


# ── Preset Scenarios ─────────────────────────────────────────────────────────

SCENARIOS = {
    "1": {
        "title": "E-commerce fraud — cardholder didn't authorize purchase",
        "description": "Jane Doe's card was used at ShadyElectronics.com for $349.99. She says she never made this purchase. The transaction was non-3DS e-commerce (ECI 7, no CAVV).",
        "dispute": lambda: Dispute(
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
                    description="Cardholder certifies she did not authorize this transaction",
                    provided_by=PartyRole.ISSUER,
                    provided_date=date.today(),
                ),
            ],
        ),
    },
    "2": {
        "title": "3DS-authenticated e-commerce — fraud claim on protected transaction",
        "description": "John Smith claims fraud on a $1,250 purchase at LuxuryGoods.com. But the transaction was authenticated via 3D Secure (ECI 5, CAVV present). Liability shift applies.",
        "dispute": lambda: Dispute(
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
    },
    "3": {
        "title": "Merchandise not received — recent online order",
        "description": "Alice ordered a gadget from GadgetStore for $89.99. It's been 10 days and she hasn't received it. She already contacted the merchant with no resolution.",
        "dispute": lambda: Dispute(
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
            condition=DisputeCondition.CONSUMER_NOT_RECEIVED,
            issuer=Party(role=PartyRole.ISSUER, name="Wells Fargo", institution_id="WF001", region=Region.US),
            acquirer=Party(role=PartyRole.ACQUIRER, name="Square", institution_id="SQ001", region=Region.US),
            cardholder=Party(role=PartyRole.CARDHOLDER, name="Alice Johnson"),
            merchant=Party(role=PartyRole.MERCHANT, name="GadgetStore Inc."),
            cardholder_financial_loss=True,
            cardholder_attempted_resolution=True,
        ),
    },
    "4": {
        "title": "Expired time limit — old transaction fraud claim",
        "description": "Bob is trying to dispute a $500 transaction from 200 days ago. He claims card-absent fraud but the 120-day filing window has long passed.",
        "dispute": lambda: Dispute(
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
            condition=DisputeCondition.FRAUD_CARD_ABSENT,
            issuer=Party(role=PartyRole.ISSUER, name="Citi", institution_id="CITI001", region=Region.US),
            acquirer=Party(role=PartyRole.ACQUIRER, name="PayPal", institution_id="PP001", region=Region.US),
            cardholder=Party(role=PartyRole.CARDHOLDER, name="Bob Williams"),
            merchant=Party(role=PartyRole.MERCHANT, name="OldMerchant LLC"),
            fraud_reported_to_visa=True,
            fraud_type=FraudType.CARD_ABSENT,
            cardholder_financial_loss=True,
        ),
    },
    "5": {
        "title": "Duplicate charge — merchant charged twice",
        "description": "Carol was charged $250 twice by the same merchant for a single purchase. She has both receipts showing the duplicate.",
        "dispute": lambda: Dispute(
            transaction=TransactionDetail(
                transaction_id="TXN-2025-00475",
                transaction_date=date.today() - timedelta(days=15),
                processing_date=date.today() - timedelta(days=14),
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
                    description="Cardholder statement identifying duplicate charge",
                    provided_by=PartyRole.ISSUER,
                    provided_date=date.today(),
                ),
                DocumentEvidence(
                    document_type="proof_of_other_payment",
                    description="Documentation identifying both transactions",
                    provided_by=PartyRole.ISSUER,
                    provided_date=date.today(),
                ),
            ],
        ),
    },
    "6": {
        "title": "Cancelled recurring subscription — merchant keeps charging",
        "description": "Dave cancelled his streaming subscription 2 months ago but the merchant charged him $14.99 again this month. He has the cancellation confirmation email.",
        "dispute": lambda: Dispute(
            transaction=TransactionDetail(
                transaction_id="TXN-2025-00476",
                transaction_date=date.today() - timedelta(days=5),
                processing_date=date.today() - timedelta(days=4),
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
                    description="Email confirmation of subscription cancellation dated 2 months ago",
                    provided_by=PartyRole.CARDHOLDER,
                    provided_date=date.today(),
                ),
                DocumentEvidence(
                    document_type="cardholder_statement",
                    description="Cardholder statement confirming cancellation and continued billing",
                    provided_by=PartyRole.ISSUER,
                    provided_date=date.today(),
                ),
            ],
        ),
    },
}


# ── Display Helpers ──────────────────────────────────────────────────────────

def show_banner():
    console.print()
    console.print(Panel.fit(
        "[bold white]VISA DISPUTES PROCESSING AGENT[/bold white]\n"
        "[dim]Interactive Mode — Autonomous Dispute Processor[/dim]\n"
        "[dim]Based on Visa Core Rules, Chapter 11 (Oct 2025)[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))


def show_menu():
    console.print("\n[bold cyan]Choose a scenario to process:[/bold cyan]\n")
    for key, scenario in SCENARIOS.items():
        console.print(f"  [bold yellow]{key}[/bold yellow]  {scenario['title']}")
    console.print(f"\n  [bold yellow]R[/bold yellow]  Browse the rule registry (all 23 conditions)")
    console.print(f"  [bold yellow]C[/bold yellow]  Create a custom dispute")
    console.print(f"  [bold yellow]Q[/bold yellow]  Quit")


def print_section(title: str):
    console.print(f"\n  [bold white on blue] {title} [/bold white on blue]")


def process_dispute(dispute: Dispute, scenario_desc: str | None = None):
    """Run a dispute through the full rule engine and display results."""
    txn = dispute.transaction

    # Header
    console.print()
    console.print(Panel(
        f"[bold]{txn.merchant_name}[/bold] | [green]${txn.amount} {txn.currency}[/green]\n"
        f"TXN: {txn.transaction_id} | Date: {txn.transaction_date}\n"
        f"Environment: {txn.environment.value} | Category: {dispute.category or 'TBD'}\n"
        f"Issuer: {dispute.issuer.name} | Acquirer: {dispute.acquirer.name}\n"
        f"Cardholder: {dispute.cardholder.name}"
        + (f"\n\n[dim]{scenario_desc}[/dim]" if scenario_desc else ""),
        title="[bold]Dispute Details[/bold]",
        border_style="white",
    ))

    # Step 1: Determine condition (if not already set)
    print_section("STEP 1: CONDITION CLASSIFICATION")
    if dispute.condition:
        rule = get_condition_rule(dispute.condition)
        console.print(f"  Pre-classified as [bold yellow]{dispute.condition.value}[/bold yellow]: {rule.name}")
    else:
        candidates = engine.determine_condition(dispute)
        if candidates:
            console.print(f"  Found {len(candidates)} matching condition(s):\n")
            for cond, conf, reason in candidates[:5]:
                bar = "=" * int(conf * 30)
                color = "green" if conf >= 0.8 else "yellow" if conf >= 0.5 else "red"
                console.print(f"  [{color}]{cond.value:6s}[/{color}] {conf:5.0%} [{color}]{bar}[/{color}]  {reason}")
            best = candidates[0]
            dispute.condition = best[0]
            console.print(f"\n  Selected: [bold yellow]{best[0].value}[/bold yellow] (confidence: {best[1]:.0%})")
        else:
            console.print("  [red]No matching condition found for this dispute.[/red]")
            console.print("  [dim]The rule engine could not match the transaction facts to a known condition.[/dim]")
            return

    # Step 2: Eligibility
    print_section("STEP 2: ELIGIBILITY CHECK")
    result = engine.evaluate_eligibility(dispute)

    if result.eligible:
        console.print(f"\n  [bold white on green] ELIGIBLE [/bold white on green]\n")
    else:
        console.print(f"\n  [bold white on red] INELIGIBLE [/bold white on red]\n")

    for reason in result.reasons:
        console.print(f"  [green]+[/green] {reason}")
    for block in result.blocking_reasons:
        console.print(f"  [red]X {block}[/red]")
    for warn in result.warnings:
        console.print(f"  [yellow]! {warn}[/yellow]")

    if result.deadline:
        days_left = (result.deadline - date.today()).days
        color = "red" if days_left <= 7 else "yellow" if days_left <= 30 else "green"
        console.print(f"\n  Filing deadline: {result.deadline} ([{color}]{days_left} days remaining[/{color}])")

    # Step 3: Invalid conditions
    print_section("STEP 3: INVALID CONDITION CHECK")
    invalid_results = engine.check_invalid_conditions(dispute)
    triggered = [(inv, expl) for inv, t, expl in invalid_results if t]
    clear = [(inv, expl) for inv, t, expl in invalid_results if not t]

    if triggered:
        for inv, expl in triggered:
            console.print(f"  [bold red]TRIGGERED[/bold red] [{inv.condition_id}] {inv.description}")
            console.print(f"           [dim]{expl}[/dim]")
    else:
        console.print(f"  [green]No invalid conditions triggered[/green]")
    console.print(f"  [dim]Checked {len(invalid_results)} conditions: {len(triggered)} triggered, {len(clear)} clear[/dim]")

    # Step 4: Documentation
    print_section("STEP 4: DOCUMENTATION REQUIREMENTS")
    docs = engine.get_required_documentation(dispute)
    if docs:
        for doc in docs:
            if doc.startswith("[REQUIRED]"):
                console.print(f"  [red]{doc}[/red]")
            else:
                console.print(f"  [dim]{doc}[/dim]")
    else:
        console.print(f"  [dim]No specific documentation requirements for this condition[/dim]")

    # Provided evidence
    if dispute.evidence:
        console.print(f"\n  [bold]Evidence on file ({len(dispute.evidence)}):[/bold]")
        for ev in dispute.evidence:
            console.print(f"    [green]+[/green] {ev.document_type}: {ev.description}")

    # Step 5: Compelling evidence
    print_section("STEP 5: COMPELLING EVIDENCE OPTIONS")
    ce_options = engine.get_compelling_evidence_options(dispute)
    if ce_options:
        console.print(f"  {len(ce_options)} compelling evidence type(s) available:\n")
        for ce in ce_options:
            console.print(f"  [cyan]{ce}[/cyan]")
    else:
        console.print(f"  [dim]No compelling evidence types defined for this condition[/dim]")

    # Step 6: Deadlines
    print_section("STEP 6: TIMELINE & DEADLINES")
    try:
        deadlines = engine.calculate_deadlines(dispute)
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold", width=22)
        table.add_column()
        table.add_row("Filing deadline", str(deadlines.dispute_deadline))
        if deadlines.wait_until:
            table.add_row("Must wait until", str(deadlines.wait_until))
        if deadlines.pre_arb_deadline:
            table.add_row("Pre-arb deadline", str(deadlines.pre_arb_deadline))
        if deadlines.max_absolute_deadline:
            table.add_row("Absolute max", str(deadlines.max_absolute_deadline))
        table.add_row("Rule", deadlines.description)
        console.print(table)
    except Exception as e:
        console.print(f"  [dim]Could not calculate deadlines: {e}[/dim]")

    # Step 7: Pipeline simulation
    print_section("STEP 7: AGENT PIPELINE")
    if result.eligible:
        console.print(f"  Running dispute through the orchestrator pipeline...\n")
        asyncio.run(_run_pipeline(dispute))
    else:
        console.print(f"  [dim]Skipping pipeline — dispute is not eligible[/dim]")

    console.print(f"\n{'='*70}")


async def _run_pipeline(dispute: Dispute):
    """Run a dispute through the orchestrator pipeline."""
    config = AppConfig()
    queue = InMemoryQueue()
    llm = DemoLLM()
    orchestrator = Orchestrator(config=config, queue=queue, llm=llm)

    await orchestrator.submit_dispute(dispute)

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
        icon = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
        console.print(f"  [{iteration:2d}] {icon} {result.decision}")

        if result.data:
            if "condition" in result.data:
                console.print(f"       Condition: {result.data['condition']} (confidence: {result.data.get('confidence', 'N/A')})")
            if "eligible" in result.data:
                console.print(f"       Eligible: {'Yes' if result.data['eligible'] else 'No'}")
            if "amount_rule" in result.data:
                console.print(f"       Amount: {result.data['amount_rule']}")

    status = await orchestrator.get_dispute_status(str(dispute.dispute_id))
    console.print(f"\n  [bold]Final:[/bold] status={status['status']}, phase={status['phase']}, tasks={len(status['tasks'])}")


def show_rule_registry():
    """Display the full rule registry."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]VISA DISPUTE CONDITIONS REGISTRY[/bold cyan]\n"
        "All 23 conditions from Chapter 11",
        border_style="cyan",
    ))

    for cat_name, cat_enum in [
        ("Category 10: Fraud", DisputeCategory.FRAUD),
        ("Category 11: Authorization", DisputeCategory.AUTHORIZATION),
        ("Category 12: Processing Errors", DisputeCategory.PROCESSING_ERRORS),
        ("Category 13: Consumer Disputes", DisputeCategory.CONSUMER_DISPUTES),
    ]:
        rules = CONDITIONS_BY_CATEGORY[cat_enum]
        table = Table(title=cat_name, show_lines=True, width=95)
        table.add_column("Code", style="bold yellow", width=5)
        table.add_column("Name", width=35)
        table.add_column("Time", style="green", width=14)
        table.add_column("Invalid", justify="center", width=7)
        table.add_column("Docs", justify="center", width=5)
        table.add_column("CE", justify="center", width=4)
        table.add_column("Prerequisites", style="dim", width=20)

        for rule in rules:
            ce = get_compelling_evidence_for_condition(rule.condition)
            tl = rule.time_limit
            time_str = f"{tl.calendar_days}d"
            if tl.max_calendar_days:
                time_str += f" (max {tl.max_calendar_days}d)"
            prereq = "; ".join(rule.prerequisites[:2]) if rule.prerequisites else "-"
            if len(prereq) > 30:
                prereq = prereq[:27] + "..."
            table.add_row(
                rule.condition.value,
                rule.name,
                time_str,
                str(len(rule.invalid_conditions)),
                str(len(rule.documentation_requirements)),
                str(len(ce)) if ce else "-",
                prereq,
            )

        console.print(table)
        console.print()


def create_custom_dispute() -> Dispute | None:
    """Walk the user through creating a custom dispute."""
    console.print("\n[bold cyan]Create a Custom Dispute[/bold cyan]\n")

    # Category
    console.print("  Categories:")
    console.print("    [yellow]10[/yellow] Fraud")
    console.print("    [yellow]11[/yellow] Authorization")
    console.print("    [yellow]12[/yellow] Processing Errors")
    console.print("    [yellow]13[/yellow] Consumer Disputes")
    cat_input = Prompt.ask("\n  Category", choices=["10", "11", "12", "13"], default="10")
    category = DisputeCategory(cat_input)

    # Condition (optional)
    conds = CONDITIONS_BY_CATEGORY[category]
    console.print(f"\n  Conditions for Category {cat_input}:")
    for rule in conds:
        console.print(f"    [yellow]{rule.condition.value}[/yellow] {rule.name}")
    cond_input = Prompt.ask(
        "\n  Condition (or press Enter for auto-detect)",
        default="",
    )
    condition = None
    if cond_input:
        try:
            condition = DisputeCondition(cond_input)
        except ValueError:
            console.print(f"  [red]Unknown condition '{cond_input}', will auto-detect[/red]")

    # Transaction details
    merchant = Prompt.ask("  Merchant name", default="TestMerchant")
    amount = Decimal(Prompt.ask("  Amount (USD)", default="100.00"))
    days_ago = IntPrompt.ask("  Transaction date (days ago)", default=30)

    env_map = {"1": TransactionEnvironment.CARD_PRESENT, "2": TransactionEnvironment.ECOMMERCE,
               "3": TransactionEnvironment.CARD_ABSENT, "4": TransactionEnvironment.ATM,
               "5": TransactionEnvironment.MAIL_PHONE, "6": TransactionEnvironment.RECURRING}
    console.print("\n  Environment:")
    console.print("    [yellow]1[/yellow] Card Present  [yellow]2[/yellow] E-Commerce  [yellow]3[/yellow] Card Absent")
    console.print("    [yellow]4[/yellow] ATM  [yellow]5[/yellow] Mail/Phone  [yellow]6[/yellow] Recurring")
    env_input = Prompt.ask("  Environment", choices=["1", "2", "3", "4", "5", "6"], default="2")
    environment = env_map[env_input]

    is_fraud = category == DisputeCategory.FRAUD
    fraud_reported = False
    fraud_type = None
    if is_fraud:
        fraud_reported = Confirm.ask("  Fraud reported to Visa?", default=True)
        fraud_type = FraudType.CARD_ABSENT if environment in (
            TransactionEnvironment.ECOMMERCE, TransactionEnvironment.CARD_ABSENT, TransactionEnvironment.MAIL_PHONE
        ) else None

    financial_loss = Confirm.ask("  Cardholder suffered financial loss?", default=True)
    attempted_resolution = Confirm.ask("  Cardholder attempted merchant resolution?", default=False)

    txn_date = date.today() - timedelta(days=days_ago)
    dispute = Dispute(
        transaction=TransactionDetail(
            transaction_id=f"TXN-CUSTOM-{days_ago:04d}",
            transaction_date=txn_date,
            processing_date=txn_date + timedelta(days=1),
            amount=amount,
            currency="USD",
            merchant_name=merchant,
            merchant_category_code="5411",
            merchant_country="US",
            environment=environment,
            is_recurring=environment == TransactionEnvironment.RECURRING,
            fraud_type_reported=fraud_type,
        ),
        category=category,
        condition=condition,
        issuer=Party(role=PartyRole.ISSUER, name="Demo Issuer", institution_id="DEMO001", region=Region.US),
        acquirer=Party(role=PartyRole.ACQUIRER, name="Demo Acquirer", institution_id="DEMO002", region=Region.US),
        cardholder=Party(role=PartyRole.CARDHOLDER, name="Demo Cardholder"),
        merchant=Party(role=PartyRole.MERCHANT, name=merchant),
        fraud_reported_to_visa=fraud_reported,
        fraud_type=fraud_type,
        cardholder_financial_loss=financial_loss,
        cardholder_attempted_resolution=attempted_resolution,
    )

    return dispute


# ── Main Loop ────────────────────────────────────────────────────────────────

def main():
    show_banner()

    while True:
        show_menu()
        choice = Prompt.ask("\n[bold]>[/bold]", default="1").strip().upper()

        if choice == "Q":
            console.print("\n[dim]Goodbye.[/dim]\n")
            break
        elif choice == "R":
            show_rule_registry()
        elif choice == "C":
            dispute = create_custom_dispute()
            if dispute:
                process_dispute(dispute)
        elif choice in SCENARIOS:
            scenario = SCENARIOS[choice]
            dispute = scenario["dispute"]()
            process_dispute(dispute, scenario["description"])
        else:
            console.print(f"  [red]Unknown option '{choice}'[/red]")


if __name__ == "__main__":
    main()
