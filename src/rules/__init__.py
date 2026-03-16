"""AI-powered dispute categorization.

This module provides the AI-powered dispute categorization engine that uses
OpenAI to reason over the Visa Core Rules document. The previous hardcoded
rules modules (validity, time_limits, documentation, compelling_evidence)
have been replaced by LLM-powered agents that reason directly over the
Visa rules text.
"""

from src.rules.categorizer import CategorizationResult, categorize_dispute

__all__ = [
    "CategorizationResult",
    "categorize_dispute",
]
