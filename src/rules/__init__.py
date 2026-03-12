"""Visa Rules Engine - Encoded dispute processing logic.

This module encodes Visa Core Rules Section 11 (Dispute Resolution) into
actionable Python logic. This is NOT a simple RAG system - it contains
deterministic rule evaluation, time limit calculations, validity checks,
documentation validators, and compelling evidence evaluation.
"""

from src.rules.categorizer import CategorizationResult, categorize_dispute
from src.rules.compelling_evidence import (
    CompellingEvidenceResult,
    evaluate_compelling_evidence,
)
from src.rules.documentation import (
    DocumentationCheckResult,
    check_documentation_requirements,
    check_fraud_type_code_requirement,
)
from src.rules.time_limits import (
    calculate_deadline,
    get_arbitration_deadline,
    get_pre_arbitration_deadline,
    is_within_time_limit,
)
from src.rules.validity import (
    ValidityCheckResult,
    check_dispute_validity,
)

__all__ = [
    "CategorizationResult",
    "CompellingEvidenceResult",
    "DocumentationCheckResult",
    "ValidityCheckResult",
    "calculate_deadline",
    "categorize_dispute",
    "check_dispute_validity",
    "check_documentation_requirements",
    "check_fraud_type_code_requirement",
    "evaluate_compelling_evidence",
    "get_arbitration_deadline",
    "get_pre_arbitration_deadline",
    "is_within_time_limit",
]
