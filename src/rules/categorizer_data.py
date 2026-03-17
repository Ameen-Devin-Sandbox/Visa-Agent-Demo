# THIS FILE IS AUTO-GENERATED from rules/generated/categorizer.yaml
# DO NOT EDIT MANUALLY. Run `python scripts/generate_rules.py` to regenerate.
# Source: Visa Core Rules V1.1 - 18 October 2025
"""Categorizer keyword data loaded from rules/generated/categorizer.yaml.

Provides keyword lists and category metadata for dispute categorization.
"""

from pathlib import Path
from typing import Any

import yaml

# Load categorizer data from YAML at import time
_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "rules"
    / "generated"
    / "categorizer.yaml"
)
with open(_YAML_PATH, encoding="utf-8") as _f:
    _CAT_DATA: dict[str, Any] = yaml.safe_load(_f)

FRAUD_INDICATORS: list[str] = _CAT_DATA.get("fraud_indicators", [])
AUTHORIZATION_INDICATORS: list[str] = _CAT_DATA.get("authorization_indicators", [])
PROCESSING_ERROR_INDICATORS: list[str] = _CAT_DATA.get(
    "processing_error_indicators", []
)
CATEGORIES: dict[str, Any] = _CAT_DATA.get("categories", {})
