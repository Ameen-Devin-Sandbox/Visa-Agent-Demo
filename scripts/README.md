# Visa Rules Extraction & Code Generation Pipeline

This directory contains scripts for extracting Visa dispute rules from the
official documentation and generating Python code from the structured YAML
representation.

## End-to-End Workflow

### 1. Drop new PDF into `docs/`

Place the updated Visa Core Rules PDF into the `docs/` directory.

### 2. Convert PDF to Markdown

Convert the PDF to markdown format:

```bash
# Use your preferred PDF-to-markdown tool
# The output should be saved as docs/visa-rules-public.md
```

### 3. Extract Rules from Markdown

Run the extraction script to produce YAML files:

```bash
python scripts/extract_rules.py
```

This reads `docs/visa-rules-public.md`, uses OpenAI's API to extract
structured rule data, and writes it to `rules/generated/*.yaml`.

**Options:**
- `--diff` — Show what changed compared to existing YAML files
- `--dry-run` — Print extracted YAML to stdout without writing files

### 4. Review YAML Diff

Review the changes to the extracted rules:

```bash
git diff rules/generated/
```

Verify that the extracted data matches your expectations. The YAML files
are the single source of truth for all rule data.

### 5. Generate Python Code

Regenerate the Python rule modules from YAML:

```bash
python scripts/generate_rules.py
```

This reads `rules/generated/*.yaml` and produces `src/rules/*.py` with
auto-generated code that loads rules from YAML at import time.

**Options:**
- `--check` — Verify files are up to date (exits with code 1 if not)

### 6. Run Tests

Validate that the regenerated rules produce identical behavior:

```bash
pytest tests/ -v
```

### 7. Commit and Deploy

```bash
git add rules/generated/ src/rules/
git commit -m "Update Visa rules from V1.X document"
```

## Directory Structure

```
rules/
├── generated/           # YAML rule files (source of truth)
│   ├── time_limits.yaml
│   ├── validity.yaml
│   ├── documentation.yaml
│   ├── compelling_evidence.yaml
│   └── categorizer.yaml
└── schemas/             # JSON Schema for validating YAML files
    ├── time_limits.schema.json
    ├── validity.schema.json
    ├── documentation.schema.json
    ├── compelling_evidence.schema.json
    └── categorizer.schema.json

scripts/
├── extract_rules.py     # PDF/Markdown → YAML extraction (uses OpenAI)
├── generate_rules.py    # YAML → Python code generation
└── README.md            # This file

src/rules/
├── __init__.py
├── categorizer.py       # AI-powered categorization (uses OpenAI directly)
├── categorizer_data.py  # Keyword data loaded from YAML
├── validity.py          # Data-driven validity checker (loaded from YAML)
├── time_limits.py       # Time limit calculations (loaded from YAML)
├── documentation.py     # Documentation requirements (loaded from YAML)
└── compelling_evidence.py  # Compelling evidence evaluation (loaded from YAML)
```

## Architecture

The pipeline follows a data-driven approach:

1. **Source Document** (`docs/visa-rules-public.md`) — The Visa Core Rules
   markdown, converted from the official PDF.

2. **Extraction** (`scripts/extract_rules.py`) — Uses OpenAI's structured
   output to extract rules into well-defined YAML schemas.

3. **YAML Rules** (`rules/generated/`) — The intermediate representation.
   Human-reviewable, diffable, and version-controlled.

4. **Code Generation** (`scripts/generate_rules.py`) — Produces Python
   modules that load rules from YAML at import time.

5. **Runtime** (`src/rules/`) — Python modules that provide the same API
   as the original hardcoded rules but load data from YAML files.

## Environment Variables

- `OPENAI_API_KEY` — Required by `extract_rules.py` for LLM-based extraction.
