# Visa Disputes Agent — Project Knowledge

## Build & Test Commands

```bash
# Setup (requires uv)
uv venv --python 3.13
uv pip install -e ".[dev]"

# Run tests
.venv/bin/python -m pytest tests/ -v

# Lint
.venv/bin/ruff check src/ tests/

# Run demo
.venv/bin/python -m src.main
```

## Architecture Notes

- Rules are encoded programmatically in `src/rules/categories/`, NOT retrieved via RAG
- LLM is used only for ambiguous judgment calls, not for rule lookup
- Queue is in-memory for now; swap to Redis/Postgres via `src/queue/base.py` interface
- LLM provider is configurable (Anthropic/OpenAI) via `.env`
- Two distinct dispute flows: Cat 10/11 (no Dispute Response stage) vs Cat 12/13 (has Dispute Response stage)

## Key Visa Rules References

- Chapter 11: Dispute Resolution (lines 50855-58253 in visa-rules-public.md)
- Section 11.7: Category 10 (Fraud) conditions
- Section 11.8: Category 11 (Authorization) conditions  
- Section 11.9: Category 12 (Processing Errors) conditions
- Section 11.10: Category 13 (Consumer Disputes) conditions
- Section 11.11-11.13: Arbitration and Compliance
- Table 11-6: Compelling Evidence (16 types)
- Tables 11-1/11-2: Process flows with time limits
