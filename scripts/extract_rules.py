#!/usr/bin/env python3
"""Extract rules from Visa Core Rules markdown into YAML schema files.

Reads docs/visa-rules-public.md, splits it into relevant sections,
and uses OpenAI's API with structured output to extract rules into
the YAML schema defined in rules/schemas/.

Usage:
    python scripts/extract_rules.py                # Extract and write YAML files
    python scripts/extract_rules.py --diff         # Show diff against existing YAML
    python scripts/extract_rules.py --dry-run      # Print extracted YAML to stdout
"""

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

import yaml

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI  # noqa: E402

RULES_MD_PATH = PROJECT_ROOT / "docs" / "visa-rules-public.md"
GENERATED_DIR = PROJECT_ROOT / "rules" / "generated"
SCHEMAS_DIR = PROJECT_ROOT / "rules" / "schemas"

SYSTEM_PROMPT = """\
You are an expert at extracting structured data from legal/regulatory documents.
Extract ONLY what is explicitly stated in the provided text. Do not infer or add
rules that are not explicitly mentioned. If something is ambiguous, note it but
do not guess.

You must respond with valid JSON matching the schema provided.
"""


def get_client() -> OpenAI:
    """Return an OpenAI client using the OPENAI_API_KEY environment variable."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key)


def load_markdown() -> str:
    """Load the Visa rules markdown document."""
    if not RULES_MD_PATH.exists():
        print(f"Error: {RULES_MD_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    return RULES_MD_PATH.read_text(encoding="utf-8")


def extract_section(text: str, section_number: str) -> str:
    """Extract a specific section from the markdown by heading number."""
    escaped = re.escape(section_number)
    pattern = rf"^(#{{{2,6}}})\s+{escaped}\s"
    match = re.search(pattern, text, re.MULTILINE)

    if match is None:
        return f"[Section {section_number} not found]"

    heading_level = len(match.group(1))
    start = match.start()

    end_pattern = rf"^#{{{1},{heading_level}}}\s"
    end_match = re.search(end_pattern, text[match.end():], re.MULTILINE)
    end = match.end() + end_match.start() if end_match is not None else len(text)

    return text[start:end].strip()


def extract_sections(text: str, section_numbers: list[str]) -> str:
    """Extract multiple sections and join them."""
    parts = [extract_section(text, s) for s in section_numbers]
    return "\n\n---\n\n".join(parts)


def load_schema(name: str) -> dict:
    """Load a JSON schema file."""
    schema_path = SCHEMAS_DIR / f"{name}.schema.json"
    if not schema_path.exists():
        print(f"Warning: Schema {schema_path} not found.", file=sys.stderr)
        return {}
    return json.loads(schema_path.read_text(encoding="utf-8"))


def call_openai(client: OpenAI, context: str, schema: dict, instruction: str) -> dict:
    """Call OpenAI API with structured output request."""
    user_prompt = f"""\
{instruction}

=== DOCUMENT TEXT ===
{context[:50000]}

=== OUTPUT JSON SCHEMA ===
{json.dumps(schema, indent=2)}

Extract the data and respond with valid JSON matching the schema above.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=8000,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty response")

    return json.loads(content)


def extract_time_limits(client: OpenAI, text: str) -> dict:
    """Extract time limits from Section 11.2."""
    context = extract_sections(text, ["11.2", "11.3", "11.4"])
    schema = load_schema("time_limits")
    return call_openai(
        client,
        context,
        schema,
        "Extract ALL dispute time limits, pre-arbitration time limits, and "
        "arbitration time limits from the text. Include regional exceptions. "
        "Use condition codes (e.g., '10.1', '13.2') as keys.",
    )


def extract_validity(client: OpenAI, text: str) -> dict:
    """Extract validity rules from Sections 11.7-11.10."""
    sections = [
        "11.7.2", "11.7.3", "11.7.4", "11.7.5",
        "11.8.1", "11.8.2", "11.8.3",
        "11.9.4", "11.9.5",
        "11.10.2", "11.10.3", "11.10.7",
    ]
    context = extract_sections(text, sections)
    schema = load_schema("validity")
    return call_openai(
        client,
        context,
        schema,
        "Extract all INVALID dispute conditions for each dispute condition code. "
        "Each invalid condition specifies a field on the transaction/case, an "
        "expected value, and a reason string. Focus on the '.3' subsections "
        "(e.g., 11.7.2.3) which list invalid dispute conditions.",
    )


def extract_documentation(client: OpenAI, text: str) -> dict:
    """Extract documentation requirements from Sections 11.7-11.10."""
    sections = [
        "11.7.2", "11.7.3", "11.7.4", "11.7.5",
        "11.8.1", "11.8.2", "11.8.3",
        "11.9.1", "11.9.2", "11.9.3", "11.9.4", "11.9.5", "11.9.6",
        "11.10.2", "11.10.3", "11.10.4", "11.10.5", "11.10.6",
        "11.10.7", "11.10.8", "11.10.9", "11.10.10",
    ]
    context = extract_sections(text, sections)
    schema = load_schema("documentation")
    return call_openai(
        client,
        context,
        schema,
        "Extract ALL documentation and certification requirements for each "
        "dispute condition. Focus on the '.5' subsections (e.g., 11.7.2.5) "
        "which list required documentation. Include cardholder letter "
        "requirements and fraud type code requirements.",
    )


def extract_compelling_evidence(client: OpenAI, text: str) -> dict:
    """Extract compelling evidence rules from Section 11.5.2-11.5.3."""
    context = extract_sections(text, ["11.5.2", "11.5.3"])
    schema = load_schema("compelling_evidence")
    return call_openai(
        client,
        context,
        schema,
        "Extract all compelling evidence types for each dispute condition. "
        "Include keyword mappings used to match evidence to types.",
    )


def extract_categorizer(client: OpenAI, text: str) -> dict:
    """Extract categorization rules from Sections 11.6-11.10."""
    context = extract_sections(text, ["11.6", "11.7.1", "11.8", "11.9", "11.10.1"])
    schema = load_schema("categorizer")
    return call_openai(
        client,
        context,
        schema,
        "Extract the dispute categories (10-13), their conditions, and "
        "keyword indicators used to identify each category type "
        "(fraud indicators, authorization indicators, processing error indicators).",
    )


def show_diff(name: str, new_content: str) -> None:
    """Show a diff between existing and new YAML content."""
    existing_path = GENERATED_DIR / f"{name}.yaml"
    if existing_path.exists():
        existing = existing_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        existing = []

    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(existing, new_lines, fromfile=f"a/{name}.yaml", tofile=f"b/{name}.yaml")
    diff_text = "".join(diff)
    if diff_text:
        print(f"\n--- Changes for {name}.yaml ---")
        print(diff_text)
    else:
        print(f"No changes for {name}.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Visa rules from markdown to YAML")
    parser.add_argument("--diff", action="store_true", help="Show diff against existing YAML files")
    parser.add_argument("--dry-run", action="store_true", help="Print YAML to stdout without writing")
    args = parser.parse_args()

    text = load_markdown()
    client = get_client()

    extractors = {
        "time_limits": extract_time_limits,
        "validity": extract_validity,
        "documentation": extract_documentation,
        "compelling_evidence": extract_compelling_evidence,
        "categorizer": extract_categorizer,
    }

    for name, extractor in extractors.items():
        print(f"Extracting {name}...", file=sys.stderr)
        try:
            data = extractor(client, text)
        except Exception as e:
            print(f"Error extracting {name}: {e}", file=sys.stderr)
            continue

        yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

        if args.diff:
            show_diff(name, yaml_content)
        elif args.dry_run:
            print(f"\n=== {name}.yaml ===")
            print(yaml_content)
        else:
            GENERATED_DIR.mkdir(parents=True, exist_ok=True)
            output_path = GENERATED_DIR / f"{name}.yaml"
            output_path.write_text(yaml_content, encoding="utf-8")
            print(f"Wrote {output_path}", file=sys.stderr)

    print("Extraction complete.", file=sys.stderr)


if __name__ == "__main__":
    main()
