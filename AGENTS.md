# Visa Disputes Agent — Project Knowledge

## Build & Test Commands

```bash
# Setup (requires uv)
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run tests by module
python -m pytest tests/test_models.py tests/test_queue.py -v          # Given (should pass)
python -m pytest tests/test_categorizer_comprehensive.py -v            # Module 1
python -m pytest tests/test_agents_comprehensive.py::TestFraudDisputeAgent -v  # Module 2
python -m pytest tests/test_agents_comprehensive.py -v                 # Module 2+3
python -m pytest tests/test_brain.py tests/test_brain_comprehensive.py -v  # Module 4
python -m pytest tests/test_api_comprehensive.py -v                    # Module 5
python -m pytest tests/test_end_to_end.py -v                          # Full E2E

# Lint
ruff check src/ tests/

# Run live demo (requires OPENAI_API_KEY)
python demo.py
```

## Architecture

- Domain-specific AI agents (fraud, auth, processing errors, consumer disputes, pre-arbitration)
- LLM (OpenAI gpt-4o-mini) reasons over Visa rules markdown injected as prompt context
- `visa_rules.py` loads and caches sections from `docs/visa-rules-public.md`
- `categorizer.py` uses LLM to determine dispute category and condition
- `brain.py` orchestrates the full lifecycle: validate → categorize → route → process
- Tests use a sophisticated mock in `conftest.py` (no real API calls)
- FastAPI API exposes all operations over HTTP

## Key Files

- `src/llm/openai_client.py` — `chat_json()` wrapper for OpenAI structured output
- `src/llm/visa_rules.py` — Extracts Visa rules sections by number
- `src/models/enums.py` — All 23 dispute conditions, categories, lifecycle stages
- `tests/conftest.py` — 665-line mock framework (autouse fixtures)
