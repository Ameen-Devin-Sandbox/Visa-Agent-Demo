"""Dispute rules engine with AI-powered categorization and YAML-driven rule evaluation.

This module provides:
- AI-powered dispute categorization (via OpenAI)
- YAML-driven validity checking, time limit calculations, documentation
  requirements, and compelling evidence evaluation

Rule data is loaded from rules/generated/*.yaml at import time. To update
the rules, modify the YAML files and run `python scripts/generate_rules.py`.
"""

from src.rules.categorizer import CategorizationResult, categorize_dispute

__all__ = [
    "CategorizationResult",
    "categorize_dispute",
]
