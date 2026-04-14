# Visa Disputes Processing Agent — Workshop

Build an autonomous AI agent system that processes Visa disputes using OpenAI and Python.

**This is a hands-on workshop** where you'll use [Devin](https://devin.ai) to implement a multi-agent dispute processing system that reasons over real Visa Core Rules.

## Quick Start

```bash
# Setup
uv venv --python 3.13 && source .venv/bin/activate
uv pip install -e ".[dev]"

# Set your OpenAI API key
cp .env.example .env
# Edit .env with your key

# Verify setup
python -m pytest tests/test_models.py tests/test_queue.py -v
```

## Workshop Guide

See **[WORKSHOP.md](WORKSHOP.md)** for the full workshop instructions, module breakdown, and Devin prompting tips.

## Architecture

```
Dispute → Brain → AI Categorizer → Domain Agent → Decision
                                        ↓
                              Fraud | Auth | Processing | Consumer
```

- **5 AI agents** specialized by dispute category
- **OpenAI gpt-4o-mini** for reasoning over Visa rules
- **23 dispute conditions** across 4 categories
- **FastAPI** REST API
- **Priority queue** with retry logic
- **~5,000 lines** of tests with sophisticated LLM mocking

## What You'll Build

| Module | Component | Devin Skill |
|--------|-----------|-------------|
| 1 | AI Categorizer | Domain document reasoning |
| 2 | Base + Fraud Agent | Agent architecture patterns |
| 3 | Auth, Consumer, Processing Agents | Pattern replication at speed |
| 4 | Brain Orchestrator | Complex orchestration logic |
| 5 | Pre-Arbitration + API | End-to-end wiring |

## Tech Stack

- Python 3.11+
- OpenAI API (gpt-4o-mini)
- FastAPI + Uvicorn
- Pydantic v2
- pytest + pytest-asyncio
