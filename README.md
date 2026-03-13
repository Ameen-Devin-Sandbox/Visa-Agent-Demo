# Visa Disputes Processing Agent

An autonomous AI agent system that processes Visa disputes according to the **Visa Core Rules and Product and Service Rules** (October 2025 edition).

## Architecture

This is **not a simple RAG system**. It encodes Visa's 23 dispute conditions as structured, programmatically-evaluable rules, and uses LLM reasoning only where human judgment is required.

```
┌─────────────────────────────────────────────────────┐
│                   Task Queue                         │
│  (Priority queue of dispute processing tasks)        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Orchestrator ("The Brain")               │
│  Routes tasks to specialized agents, manages          │
│  dispute lifecycle, handles retries & follow-ups      │
└───┬──────────┬──────────┬──────────┬────────────────┘
    │          │          │          │
┌───▼───┐ ┌───▼───┐ ┌───▼────┐ ┌──▼────────┐
│Intake │ │Invest.│ │Resoln. │ │Escalation │
│Agent  │ │Agent  │ │Agent   │ │Agent      │
└───┬───┘ └───┬───┘ └───┬────┘ └──┬────────┘
    │         │         │         │
┌───▼─────────▼─────────▼─────────▼──────────┐
│            Rule Engine                       │
│  Programmatic evaluation of all 23 dispute   │
│  conditions, time limits, invalid checks     │
├──────────────────────────────────────────────┤
│            LLM Layer (Claude / GPT)          │
│  Used for ambiguous cases requiring judgment │
└──────────────────────────────────────────────┘
```

### Agents

| Agent | Responsibility |
|-------|---------------|
| **Intake** | Determines dispute condition code, validates prerequisites, checks eligibility |
| **Investigation** | Evaluates evidence, checks invalid conditions, reviews compelling evidence |
| **Resolution** | Files disputes, evaluates responses, handles pre-arbitration |
| **Escalation** | Prepares arbitration and compliance filings |

### Encoded Rules

All **23 dispute conditions** across 4 categories are fully encoded:

- **Category 10: Fraud** (10.1-10.5) — EMV counterfeit, non-counterfeit, card-present, card-absent, VFMP
- **Category 11: Authorization** (11.1-11.3) — CRB, declined auth, no auth/late presentment
- **Category 12: Processing Errors** (12.2-12.7) — Incorrect code/currency/account/amount, duplicate, invalid data
- **Category 13: Consumer Disputes** (13.1-13.9) — Not received, cancelled recurring, not as described, counterfeit merch, misrepresentation, credit not processed, cancelled, OCT, ATM non-receipt

Each condition includes:
- Trigger criteria
- Prerequisites
- Time limits (75 or 120 calendar days, with 540-day caps)
- Invalid dispute conditions (up to 18 for condition 10.4)
- Documentation requirements
- Pre-arbitration / dispute response rights
- Compelling evidence applicability (16 types from Table 11-6)
- Regional variations

## Setup

```bash
# Install uv (if not installed)
brew install uv

# Create venv and install dependencies
uv venv --python 3.13
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Run the demo with sample disputes
.venv/bin/python -m src.main

# Run tests
.venv/bin/python -m pytest tests/ -v

# Lint
.venv/bin/ruff check src/ tests/
```

## Project Structure

```
src/
├── config.py                      # App configuration
├── main.py                        # Entry point + demo
├── models/
│   ├── dispute.py                 # Dispute, Transaction, Party models
│   ├── enums.py                   # All enumerations (23 conditions, phases, etc.)
│   └── task.py                    # Task queue models
├── rules/
│   ├── engine.py                  # Rule evaluation engine
│   ├── registry.py                # Central rule index + compelling evidence
│   ├── models.py                  # Rule data models
│   └── categories/
│       ├── fraud.py               # Category 10 rules (5 conditions)
│       ├── authorization.py       # Category 11 rules (3 conditions)
│       ├── processing_errors.py   # Category 12 rules (6 conditions)
│       └── consumer.py            # Category 13 rules (9 conditions)
├── agents/
│   ├── base.py                    # Base agent with LLM integration
│   ├── orchestrator.py            # The Brain — central orchestration
│   ├── intake.py                  # Dispute intake agent
│   ├── investigation.py           # Evidence evaluation agent
│   ├── resolution.py              # Filing and resolution agent
│   └── escalation.py              # Arbitration/compliance agent
├── llm/
│   ├── base.py                    # Abstract LLM interface
│   ├── factory.py                 # Provider factory
│   ├── anthropic.py               # Claude integration
│   └── openai.py                  # GPT integration
├── queue/
│   ├── base.py                    # Abstract queue interface
│   └── memory.py                  # In-memory priority queue
└── tools/
    └── executor.py                # Agent tool definitions and execution
```

## How It Works

1. **Dispute Submitted** → Orchestrator creates an initial `DETERMINE_DISPUTE_CONDITION` task
2. **Intake Agent** analyzes transaction facts and determines the condition code (e.g., 10.4 for card-absent fraud)
3. **Intake Agent** evaluates eligibility — checks financial loss, fraud reporting, invalid conditions, time limits
4. **Investigation Agent** deep-checks all invalid conditions and reviews compelling evidence
5. **Resolution Agent** files the dispute, evaluates responses, manages pre-arbitration
6. **Escalation Agent** handles arbitration and compliance if needed

The rule engine makes **deterministic decisions** where possible (time limit expired? mobile push payment? 35-dispute cap?). It delegates to the **LLM only for judgment calls** (is this compelling evidence sufficient? should we proceed to arbitration?).

## Two Dispute Flows

**Flow A (Cat 10 Fraud / Cat 11 Authorization):**
Dispute → Pre-Arbitration Attempt (Acquirer, 30d) → Pre-Arb Response (Issuer, 30d) → Arbitration (10d)

**Flow B (Cat 12 Processing Errors / Cat 13 Consumer):**
Dispute → Dispute Response (Acquirer, 30d) → Pre-Arb Attempt (Issuer, 30d) → Pre-Arb Response (Acquirer, 30d) → Arbitration (10d)

## Source

Rules encoded from the [Visa Core Rules and Visa Product and Service Rules](https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf) (18 October 2025, V1.1). The full document is available in `visa-rules-public.md`.
