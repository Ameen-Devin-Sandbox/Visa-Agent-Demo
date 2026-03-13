"""Agent tools — functions that agents can invoke during dispute processing."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.models.dispute import Dispute
from src.models.enums import DisputeCondition
from src.rules.engine import RuleEngine
from src.rules.registry import get_compelling_evidence_for_condition, get_condition_rule

engine = RuleEngine()

# Tool definitions in Anthropic/OpenAI function-calling format
AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "evaluate_eligibility",
        "description": "Evaluate whether a dispute is eligible to be filed based on Visa Rules. Checks financial loss, prerequisites, invalid conditions, time limits, and documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID to evaluate"},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "determine_dispute_condition",
        "description": "Analyze dispute facts to determine the applicable Visa dispute condition code (e.g., 10.4, 13.1). Returns ranked candidates with confidence scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID"},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "check_invalid_conditions",
        "description": "Check all invalid dispute conditions for a specific condition code. Returns which conditions are triggered and which pass.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID"},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "calculate_deadlines",
        "description": "Calculate all relevant deadlines: filing deadline, wait period, pre-arbitration deadline, arbitration deadline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID"},
                "reference_date": {"type": "string", "description": "Optional reference date (YYYY-MM-DD). Defaults to transaction processing date."},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "get_required_documentation",
        "description": "Get the list of required and optional documentation for the dispute condition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID"},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "get_compelling_evidence",
        "description": "Get available compelling evidence types for the dispute condition (Table 11-6).",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_code": {"type": "string", "description": "The dispute condition code (e.g., '10.4')"},
            },
            "required": ["condition_code"],
        },
    },
    {
        "name": "lookup_rule",
        "description": "Look up the complete rule details for a specific dispute condition code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_code": {"type": "string", "description": "The dispute condition code (e.g., '10.4', '13.1')"},
            },
            "required": ["condition_code"],
        },
    },
    {
        "name": "calculate_dispute_amount",
        "description": "Determine the maximum allowable dispute amount based on the condition rules and transaction details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute case ID"},
            },
            "required": ["dispute_id"],
        },
    },
]


class ToolExecutor:
    """Executes agent tools against dispute data."""

    def __init__(self, disputes: dict[str, Dispute]) -> None:
        self._disputes = disputes

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result."""
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler(**args)
        except Exception as e:
            return {"error": str(e)}

    def _tool_evaluate_eligibility(self, dispute_id: str) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        result = engine.evaluate_eligibility(dispute)
        return {
            "eligible": result.eligible,
            "condition": result.condition.value if result.condition else None,
            "reasons": result.reasons,
            "blocking_reasons": result.blocking_reasons,
            "warnings": result.warnings,
            "deadline": str(result.deadline) if result.deadline else None,
            "wait_until": str(result.wait_until) if result.wait_until else None,
            "required_documentation": result.required_documentation,
            "rule_references": result.rule_references,
        }

    def _tool_determine_dispute_condition(self, dispute_id: str) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        candidates = engine.determine_condition(dispute)
        return {
            "candidates": [
                {"condition": c.value, "confidence": conf, "reasoning": reason}
                for c, conf, reason in candidates
            ]
        }

    def _tool_check_invalid_conditions(self, dispute_id: str) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        results = engine.check_invalid_conditions(dispute)
        return {
            "invalid_conditions": [
                {
                    "condition_id": inv.condition_id,
                    "description": inv.description,
                    "triggered": triggered,
                    "explanation": explanation,
                }
                for inv, triggered, explanation in results
            ]
        }

    def _tool_calculate_deadlines(
        self, dispute_id: str, reference_date: str | None = None
    ) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        ref = date.fromisoformat(reference_date) if reference_date else None
        result = engine.calculate_deadlines(dispute, ref)
        return {
            "dispute_deadline": str(result.dispute_deadline),
            "wait_until": str(result.wait_until) if result.wait_until else None,
            "pre_arb_deadline": str(result.pre_arb_deadline) if result.pre_arb_deadline else None,
            "arbitration_deadline": str(result.arbitration_deadline) if result.arbitration_deadline else None,
            "max_absolute_deadline": str(result.max_absolute_deadline) if result.max_absolute_deadline else None,
            "description": result.description,
        }

    def _tool_get_required_documentation(self, dispute_id: str) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        docs = engine.get_required_documentation(dispute)
        return {"documentation": docs}

    def _tool_get_compelling_evidence(self, condition_code: str) -> dict[str, Any]:
        condition = DisputeCondition(condition_code)
        items = get_compelling_evidence_for_condition(condition)
        return {
            "compelling_evidence": [
                {
                    "item_number": ce.item_number,
                    "description": ce.description,
                    "sub_requirements": ce.sub_requirements,
                }
                for ce in items
            ]
        }

    def _tool_lookup_rule(self, condition_code: str) -> dict[str, Any]:
        condition = DisputeCondition(condition_code)
        rule = get_condition_rule(condition)
        return {
            "condition": rule.condition.value,
            "name": rule.name,
            "description": rule.description,
            "section": rule.rule_section,
            "triggers": rule.triggers,
            "prerequisites": rule.prerequisites,
            "time_limit": {
                "calendar_days": rule.time_limit.calendar_days,
                "from_event": rule.time_limit.from_event,
                "wait_days_before": rule.time_limit.wait_days_before,
                "max_calendar_days": rule.time_limit.max_calendar_days,
                "description": rule.time_limit.description,
            },
            "dispute_amount_rule": rule.dispute_amount_rule,
            "invalid_conditions_count": len(rule.invalid_conditions),
            "documentation_requirements": [
                {"description": d.description, "mandatory": d.is_mandatory}
                for d in rule.documentation_requirements
            ],
            "environments": [e.value for e in rule.environments],
            "special_notes": rule.special_notes,
            "has_dispute_response": rule.dispute_response_rights is not None,
        }

    def _tool_calculate_dispute_amount(self, dispute_id: str) -> dict[str, Any]:
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}
        if not dispute.condition:
            return {"error": "No dispute condition set"}
        rule = get_condition_rule(dispute.condition)
        return {
            "amount_rule": rule.dispute_amount_rule,
            "transaction_amount": str(dispute.transaction.amount),
            "currency": dispute.transaction.currency,
        }
