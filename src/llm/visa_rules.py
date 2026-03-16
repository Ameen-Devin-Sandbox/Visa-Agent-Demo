"""Visa rules document loader and section extractor.

Loads the Visa Core Rules markdown document and extracts relevant sections
for use as context in LLM-powered dispute processing agents.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the Visa rules markdown document relative to the project root
_RULES_DOC_PATH = Path(__file__).parent.parent.parent / "docs" / "visa-rules-public.md"

# Cache for loaded sections
_section_cache: dict[str, str] = {}
_full_text: str | None = None


def _load_full_text() -> str:
    """Load the full Visa rules document text (cached)."""
    global _full_text
    if _full_text is not None:
        return _full_text

    if not _RULES_DOC_PATH.exists():
        raise FileNotFoundError(
            f"Visa rules document not found at {_RULES_DOC_PATH}. "
            "Ensure docs/visa-rules-public.md exists in the project root."
        )

    _full_text = _RULES_DOC_PATH.read_text(encoding="utf-8")
    logger.info("Loaded Visa rules document: %d characters", len(_full_text))
    return _full_text


def get_section(section_number: str) -> str:
    """Extract a specific section from the Visa rules document.

    Args:
        section_number: The section number to extract, e.g. "11.7" or "11.10.2".
            Extracts the heading and all content until the next heading at the
            same or higher level.

    Returns:
        The extracted section text, or a fallback message if not found.
    """
    if section_number in _section_cache:
        return _section_cache[section_number]

    text = _load_full_text()

    # Build a regex to find the section heading
    # Sections appear as markdown headings like "### 11.7 ..." or "#### 11.7.2 ..."
    escaped = re.escape(section_number)
    pattern = rf"^(#{2,6})\s+{escaped}\s"
    match = re.search(pattern, text, re.MULTILINE)

    if match is None:
        fallback = f"[Section {section_number} not found in Visa rules document]"
        _section_cache[section_number] = fallback
        return fallback

    heading_level = len(match.group(1))  # Number of # characters
    start = match.start()

    # Find the end: next heading at same or higher level
    end_pattern = rf"^#{{{1},{heading_level}}}\s"
    end_match = re.search(end_pattern, text[match.end() :], re.MULTILINE)
    end = match.end() + end_match.start() if end_match is not None else len(text)

    section_text = text[start:end].strip()
    _section_cache[section_number] = section_text
    logger.debug("Extracted section %s: %d characters", section_number, len(section_text))
    return section_text


def get_dispute_overview() -> str:
    """Get the dispute resolution overview sections (11.1-11.6).

    Returns a condensed overview of the dispute resolution process, categories,
    and general requirements.
    """
    sections = [
        get_section("11.1"),
        get_section("11.2"),
        get_section("11.5"),
        get_section("11.6"),
    ]
    return "\n\n---\n\n".join(sections)


def get_fraud_rules() -> str:
    """Get the fraud dispute rules (Section 11.7)."""
    return get_section("11.7")


def get_authorization_rules() -> str:
    """Get the authorization dispute rules (Section 11.8)."""
    return get_section("11.8")


def get_processing_errors_rules() -> str:
    """Get the processing errors dispute rules (Section 11.9)."""
    return get_section("11.9")


def get_consumer_disputes_rules() -> str:
    """Get the consumer disputes rules (Section 11.10)."""
    return get_section("11.10")


def get_arbitration_rules() -> str:
    """Get the arbitration rules (Section 11.11)."""
    return get_section("11.11")


def get_compelling_evidence_rules() -> str:
    """Get the compelling evidence rules (Section 11.5.2)."""
    return get_section("11.5.2")


def get_categorization_context() -> str:
    """Get the context needed for dispute categorization.

    Returns the dispute categories table and condition descriptions,
    plus an overview of each category.
    """
    parts = [
        get_section("11.6"),
        "--- CATEGORY 10: FRAUD ---",
        get_section("11.7.1"),
        get_section("11.7.2"),
        get_section("11.7.3"),
        get_section("11.7.4"),
        get_section("11.7.5"),
        get_section("11.7.6"),
        "--- CATEGORY 11: AUTHORIZATION ---",
        get_section("11.8.1"),
        get_section("11.8.2"),
        get_section("11.8.3"),
        "--- CATEGORY 12: PROCESSING ERRORS ---",
        get_section("11.9.1"),
        get_section("11.9.2"),
        get_section("11.9.3"),
        get_section("11.9.4"),
        get_section("11.9.5"),
        get_section("11.9.6"),
        "--- CATEGORY 13: CONSUMER DISPUTES ---",
        get_section("11.10.1"),
        get_section("11.10.2"),
        get_section("11.10.3"),
        get_section("11.10.4"),
        get_section("11.10.5"),
        get_section("11.10.6"),
        get_section("11.10.7"),
        get_section("11.10.8"),
        get_section("11.10.9"),
        get_section("11.10.10"),
    ]
    return "\n\n".join(parts)


def get_condition_rules(condition_code: str) -> str:
    """Get the specific rules for a dispute condition.

    Args:
        condition_code: The condition code like "10.1", "11.3", "13.4" etc.

    Returns:
        The rules section for that specific condition.
    """
    # Map condition codes to their Visa rules section numbers
    section_map: dict[str, str] = {
        "10.1": "11.7.2",
        "10.2": "11.7.3",
        "10.3": "11.7.4",
        "10.4": "11.7.5",
        "10.5": "11.7.6",
        "11.1": "11.8.1",
        "11.2": "11.8.2",
        "11.3": "11.8.3",
        "12.2": "11.9.1",
        "12.3": "11.9.2",
        "12.4": "11.9.3",
        "12.5": "11.9.4",
        "12.6": "11.9.5",
        "12.7": "11.9.6",
        "13.1": "11.10.2",
        "13.2": "11.10.3",
        "13.3": "11.10.4",
        "13.4": "11.10.5",
        "13.5": "11.10.6",
        "13.6": "11.10.7",
        "13.7": "11.10.8",
        "13.8": "11.10.9",
        "13.9": "11.10.10",
    }

    section = section_map.get(condition_code)
    if section is None:
        return f"[No rules section mapping for condition {condition_code}]"

    return get_section(section)
