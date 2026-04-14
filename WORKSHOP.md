# Building an AI Disputes Agent with Devin

## Workshop Overview

In this workshop, you'll build an autonomous AI agent system that processes Visa disputes according to real Visa Core Rules — using **Devin** to accelerate your engineering.

The system uses OpenAI (gpt-4o-mini) to reason over Visa's dispute rules, categorize disputes, and render decisions with rule citations. By the end, you'll have a working FastAPI service that can process any of the 23 Visa dispute conditions.

**What you'll learn:**
- How to use Devin to implement complex domain-specific logic
- How to write effective prompts for Devin
- How AI agents can reason over regulatory documents
- Patterns for LLM-powered decision systems

## Architecture

```
Dispute Submitted
       |
       v
  [DisputeBrain]  ── orchestrates the full lifecycle
       |
       v
  [AI Categorizer]  ── LLM determines category + condition
       |
       v
  [Domain Agent]  ── specialized per category:
       |              - FraudDisputeAgent (Cat 10)
       |              - AuthorizationDisputeAgent (Cat 11)
       |              - ProcessingErrorsAgent (Cat 12)
       |              - ConsumerDisputesAgent (Cat 13)
       |              - PreArbitrationAgent
       v
  [Decision]  ── resolution + rule citations + confidence
       |
       v
  [RESOLVED] or [HUMAN_REVIEW]
```

## Setup

```bash
# 1. Clone and enter the repo
cd Visa-Agent-Demo
git checkout workshop

# 2. Create a virtual environment
uv venv --python 3.13
source .venv/bin/activate

# 3. Install dependencies
uv pip install -e ".[dev]"

# 4. Set your OpenAI API key (for the live demo at the end)
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 5. Verify the infrastructure works
python -m pytest tests/test_models.py tests/test_queue.py -v
```

The model and queue tests should pass. Everything else will fail — that's what you'll build!

## What's Already Built (Given to You)

These files are **complete** and ready to use:

| Component | Files | Purpose |
|-----------|-------|---------|
| **Data Models** | `src/models/` | Pydantic models for disputes, transactions, evidence, decisions |
| **Enums** | `src/models/enums.py` | All 23 dispute conditions, categories, lifecycle stages |
| **Task Queue** | `src/queue/task_queue.py` | Priority-based async queue with retry logic |
| **OpenAI Client** | `src/llm/openai_client.py` | `chat_json()` / `chat_text()` wrappers |
| **Visa Rules Loader** | `src/llm/visa_rules.py` | Extracts sections from `docs/visa-rules-public.md` |
| **API Schemas** | `src/api/schemas.py` | Request/response models for the REST API |
| **App Entry** | `src/app.py` | FastAPI app with lifecycle management |
| **Test Infrastructure** | `tests/conftest.py` | Sophisticated mock that replaces OpenAI calls in tests |

## What You'll Build (5 Modules)

Each module has TODO markers in the code and tests to verify your implementation. Use Devin to implement each one!

---

### Module 1: AI Categorizer
**File:** `src/rules/categorizer.py`
**Tests:** `python -m pytest tests/test_categorizer_comprehensive.py -v`

The categorizer uses the LLM to analyze a dispute and determine the correct Visa category (10-13) and specific condition (e.g., 10.4, 13.1).

**What to implement:**
- `_SYSTEM_PROMPT` — instructs the LLM on all 23 conditions and how to categorize
- `categorize_dispute()` — calls the LLM and parses the result
- `_build_case_prompt()` — formats case details into a prompt

**Suggested Devin prompt:**
> Implement the categorizer in `src/rules/categorizer.py`. Look at the TODO comments for what's needed. The categorizer should use `chat_json()` from `src/llm/openai_client` to call the LLM, passing dispute case details and Visa rules context from `get_categorization_context()`. The system prompt should list all 23 Visa dispute conditions across categories 10-13 and instruct the LLM to return JSON with category, condition, confidence, rationale, and alternative_conditions. Look at `src/models/enums.py` for the complete list of conditions. Run `python -m pytest tests/test_categorizer_comprehensive.py -v` to verify.

---

### Module 2: Base Agent + Fraud Agent
**Files:** `src/agents/base_agent.py`, `src/agents/fraud_agent.py`
**Tests:** `python -m pytest tests/test_agents_comprehensive.py::TestFraudDisputeAgent -v`

The base agent provides the shared LLM evaluation logic. The fraud agent processes Category 10 disputes.

**What to implement:**
- `BaseDisputeAgent.create_decision()` — creates a `DisputeDecision` object
- `BaseDisputeAgent._should_escalate_to_human()` — confidence < 0.70 or amount > $25k
- `BaseDisputeAgent._evaluate_dispute_with_llm()` — builds prompt with case details, calls `chat_json()`
- `FraudDisputeAgent.validate()` — checks condition is Category 10
- `FraudDisputeAgent.process()` — full processing pipeline with LLM evaluation
- `_FRAUD_SYSTEM_PROMPT` — instructs LLM to evaluate fraud disputes per Section 11.7

**Suggested Devin prompt:**
> Implement the base agent and fraud agent. In `src/agents/base_agent.py`, implement the 3 TODO methods: `create_decision` (returns a DisputeDecision), `_should_escalate_to_human` (escalate if confidence < 0.70 or dispute amount > 25000), and `_evaluate_dispute_with_llm` (build a detailed prompt with all case fields and call `chat_json`). Then in `src/agents/fraud_agent.py`, implement `validate` (check condition is Category 10 fraud), `process` (advance stages, call LLM, parse citations, create decision), and write the `_FRAUD_SYSTEM_PROMPT` for evaluating fraud disputes per Visa Section 11.7. Look at the DisputeDecision and RuleEvaluationResult models in `src/models/dispute.py`. Run `python -m pytest tests/test_agents_comprehensive.py::TestFraudDisputeAgent -v` to verify.

---

### Module 3: Remaining Domain Agents
**Files:** `src/agents/authorization_agent.py`, `src/agents/consumer_disputes_agent.py`, `src/agents/processing_errors_agent.py`
**Tests:** `python -m pytest tests/test_agents_comprehensive.py::TestAuthorizationDisputeAgent tests/test_agents_comprehensive.py::TestConsumerDisputesAgent tests/test_agents_comprehensive.py::TestProcessingErrorsAgent -v`

These follow the exact same pattern as the fraud agent, just with different categories and system prompts.

**What to implement:**
- Each agent's `validate()`, `process()`, and system prompt
- Authorization: Section 11.8, conditions 11.1-11.3
- Consumer Disputes: Section 11.10, conditions 13.1-13.9
- Processing Errors: Section 11.9, conditions 12.2-12.7

**Suggested Devin prompt:**
> Implement the three remaining agents in `src/agents/`: `authorization_agent.py`, `consumer_disputes_agent.py`, and `processing_errors_agent.py`. Each follows the exact same pattern as the fraud agent in `src/agents/fraud_agent.py` — look at that file as a reference. Each needs a system prompt specific to its Visa rules section, a `validate()` method that checks the condition category, and a `process()` method that follows the same pipeline. Use `get_authorization_rules()`, `get_consumer_disputes_rules()`, and `get_processing_errors_rules()` respectively for rules context. Run `python -m pytest tests/test_agents_comprehensive.py -v` to verify all agents.

**This is where Devin shines** — it can replicate the pattern across all three agents in seconds, something that would take a human 30+ minutes of copy-paste-modify.

---

### Module 4: The Brain (Orchestrator)
**File:** `src/orchestrator/brain.py`
**Tests:** `python -m pytest tests/test_brain.py tests/test_brain_comprehensive.py -v`

The Brain ties everything together — it validates disputes, runs the categorizer, routes to the right agent, and manages the lifecycle.

**What to implement:**
- Agent initialization and category-to-agent mapping
- `submit_dispute()` — queue-based intake
- `process_single()` — direct processing for tests/API
- `get_case_summary()` — summary dict for API responses
- `escalate_to_pre_arbitration()` / `escalate_to_arbitration()`
- `approve_human_review()` — human-in-the-loop
- `_execute_dispute_processing()` — the 3-stage pipeline (validate → categorize → process)
- `_validate_case()` / `_get_agent_for_case()` — helpers

**Suggested Devin prompt:**
> Implement the DisputeBrain orchestrator in `src/orchestrator/brain.py`. Fill in all TODO methods. The __init__ should initialize 5 agents (FraudDisputeAgent, AuthorizationDisputeAgent, ProcessingErrorsAgent, ConsumerDisputesAgent, PreArbitrationAgent) mapped by AgentType values, and create a category-to-agent mapping for the 4 categories. The key method is `_execute_dispute_processing` which runs a 3-stage pipeline: (1) validate case data, (2) categorize dispute using `categorize_dispute()` from `src/rules/categorizer`, (3) route to the correct agent via `_get_agent_for_case()` and call `agent.process()`. Also implement submit_dispute (enqueue), process_single (direct), get_case_summary, escalation methods, and approve_human_review. Run `python -m pytest tests/test_brain.py tests/test_brain_comprehensive.py -v` to verify.

---

### Module 5: Pre-Arbitration Agent + API Routes
**Files:** `src/agents/pre_arbitration_agent.py`, `src/api/routes.py`
**Tests:** `python -m pytest tests/test_agents_comprehensive.py::TestPreArbitrationAgent tests/test_api_comprehensive.py -v`

The pre-arbitration agent handles dispute escalation. The API routes expose everything over HTTP.

**What to implement:**
- Pre-arb agent: validate, process (routing by stage), all processing methods
- API routes: all CRUD endpoints for disputes, escalation, human review, evidence

**Suggested Devin prompt (pre-arb agent):**
> Implement the PreArbitrationAgent in `src/agents/pre_arbitration_agent.py`. This agent handles 3 stages: PRE_ARBITRATION, PRE_ARBITRATION_RESPONSE, and ARBITRATION. The `process()` method should route to the correct handler based on `case.stage`. For pre-arbitration: increment attempts, get rules from `get_compelling_evidence_rules()` + `get_arbitration_rules()`, evaluate with LLM, apply result. For arbitration: set `arbitration_filed=True`, evaluate, create ESCALATED_ARBITRATION decision with human review. The `_evaluate_pre_arb_with_llm` builds a custom prompt with case details, evidence split by party, and processing notes. The `_apply_pre_arb_result` handles next_action routing (resolved, awaiting_issuer_response, escalate_arbitration, human_review). Look at the test expectations in `tests/test_agents_comprehensive.py::TestPreArbitrationAgent`. Run those tests to verify.

**Suggested Devin prompt (API routes):**
> Implement the API routes in `src/api/routes.py`. All TODO endpoints need implementations. Use the schemas from `src/api/schemas.py` and the DisputeBrain from `get_brain()`. The submit_dispute endpoint should build a DisputeCase from the request schemas (TransactionDetails, CardholderInfo, DisputeEvidence), call `brain.process_single()`, and return a summary. Other endpoints are simpler CRUD operations. Raise HTTPException(404) when cases aren't found. Run `python -m pytest tests/test_api_comprehensive.py -v` to verify.

---

## Final Verification

Once all modules are implemented, run the full test suite:

```bash
python -m pytest tests/ -v
```

All tests should pass! Then try the live demo:

```bash
# Make sure OPENAI_API_KEY is set in .env
python demo.py
```

This will process 4 different dispute types with real OpenAI calls and show the full decision pipeline.

## End-to-End Test

```bash
python -m pytest tests/test_end_to_end.py -v
```

This runs 10 complete scenarios covering fraud, authorization, processing errors, consumer disputes, escalation, time limits, and more.

---

## Tips for Working with Devin

1. **Be specific about file paths** — tell Devin exactly which files to modify
2. **Reference existing patterns** — "follow the same pattern as fraud_agent.py"
3. **Point to tests** — "run this test command to verify"
4. **Point to models** — "look at the enums and models in src/models/"
5. **Iterate quickly** — if tests fail, paste the failure and ask Devin to fix it
6. **Let Devin read the codebase** — it's good at understanding existing code and replicating patterns

## Project Structure

```
src/
├── agents/                    # [YOU BUILD] Domain-specific AI agents
│   ├── base_agent.py         #   Abstract base with LLM evaluation
│   ├── fraud_agent.py        #   Category 10: Fraud
│   ├── authorization_agent.py #  Category 11: Authorization
│   ├── consumer_disputes_agent.py # Category 13: Consumer
│   ├── processing_errors_agent.py # Category 12: Processing Errors
│   └── pre_arbitration_agent.py   # Pre-arb & Arbitration
├── api/                       # [YOU BUILD] REST API
│   ├── routes.py             #   FastAPI endpoints
│   └── schemas.py            #   [GIVEN] Request/response models
├── llm/                       # [GIVEN] LLM integration
│   ├── openai_client.py      #   OpenAI wrapper (chat_json)
│   └── visa_rules.py         #   Visa rules document loader
├── models/                    # [GIVEN] Data models
│   ├── dispute.py            #   DisputeCase, TransactionDetails, etc.
│   ├── enums.py              #   23 conditions, categories, stages
│   └── task.py               #   Queue task model
├── orchestrator/              # [YOU BUILD] Central orchestration
│   └── brain.py              #   DisputeBrain
├── queue/                     # [GIVEN] Task queue
│   └── task_queue.py         #   Priority async queue
├── rules/                     # [YOU BUILD] AI categorization
│   └── categorizer.py        #   LLM-powered categorizer
└── app.py                     # [GIVEN] FastAPI app entry point

tests/
├── conftest.py               # [GIVEN] Sophisticated mock framework
├── test_models.py            # [GIVEN] Should pass immediately
├── test_queue.py             # [GIVEN] Should pass immediately
├── test_categorizer_comprehensive.py  # Module 1 verification
├── test_agents_comprehensive.py       # Module 2, 3, 5 verification
├── test_brain.py                      # Module 4 verification
├── test_brain_comprehensive.py        # Module 4 verification
├── test_api_comprehensive.py          # Module 5 verification
└── test_end_to_end.py                 # Final verification
```
