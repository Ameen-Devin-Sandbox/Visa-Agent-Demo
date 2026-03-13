"""Intake agent — validates incoming disputes and determines the condition code."""

from __future__ import annotations

import logging
from datetime import date

from src.agents.base import BaseAgent
from src.models.dispute import Dispute
from src.models.enums import DisputeCondition, DisputeStatus, TaskType
from src.models.task import DisputeTask, TaskResult
from src.rules.engine import RuleEngine

logger = logging.getLogger(__name__)

engine = RuleEngine()


class IntakeAgent(BaseAgent):
    """Handles dispute intake: validates prerequisites, determines condition code,
    checks eligibility, and prepares the dispute for processing."""

    agent_name = "intake"
    system_prompt = """You are a Visa disputes intake specialist. Your role is to:
1. Analyze incoming dispute cases
2. Determine the correct Visa dispute condition code based on the facts
3. Verify all prerequisites are met before filing
4. Identify any blocking conditions that would make the dispute invalid

You have deep knowledge of Visa Core Rules Chapter 11 (Dispute Resolution).
You must be precise about condition codes, time limits, and invalid dispute conditions.
When in doubt, err on the side of flagging potential issues rather than missing them.

Key rules:
- A dispute must NOT be filed unless the cardholder has suffered financial loss (except Cat 11, 12.4, 13.8)
- Fraud disputes require prior fraud reporting to Visa
- Consumer disputes often require a 15-day wait period
- Never file an invalid dispute — check ALL invalid conditions
- One dispute per transaction (except 10.5 VFMP)
"""

    async def process(self, task: DisputeTask) -> TaskResult:
        """Process an intake task."""
        dispute_id = str(task.dispute_id)
        dispute = self._disputes.get(dispute_id)

        if not dispute:
            return TaskResult(
                success=False,
                decision="BLOCKED",
                reasoning=f"Dispute {dispute_id} not found in active disputes",
            )

        if task.task_type == TaskType.DETERMINE_DISPUTE_CONDITION:
            return await self._determine_condition(dispute)
        elif task.task_type == TaskType.EVALUATE_ELIGIBILITY:
            return await self._evaluate_eligibility(dispute)
        elif task.task_type == TaskType.VALIDATE_DOCUMENTATION:
            return await self._validate_documentation(dispute)
        else:
            return TaskResult(
                success=False,
                decision="UNSUPPORTED",
                reasoning=f"Intake agent does not handle task type: {task.task_type}",
            )

    async def _determine_condition(self, dispute: Dispute) -> TaskResult:
        """Determine the dispute condition code."""
        # First, use the rule engine for programmatic matching
        candidates = engine.determine_condition(dispute)

        if not candidates:
            # Fall back to LLM reasoning
            summary = self._format_dispute_summary(dispute)
            llm_analysis = await self._reason(
                "Based on the following dispute details, determine the most appropriate Visa dispute "
                "condition code. Consider all 23 conditions across categories 10-13. "
                "Provide your top 3 candidates with confidence scores and reasoning.",
                context=summary,
            )
            return TaskResult(
                success=True,
                decision="LLM_ANALYSIS_NEEDED",
                reasoning=llm_analysis,
                next_actions=["Human review recommended — no programmatic match found"],
                data={"llm_analysis": llm_analysis},
            )

        top_condition, top_confidence, top_reasoning = candidates[0]

        # If high confidence, set it directly
        if top_confidence >= 0.8:
            dispute.condition = top_condition
            dispute.category = top_condition.category
            return TaskResult(
                success=True,
                decision=f"CONDITION_DETERMINED: {top_condition.value}",
                reasoning=top_reasoning,
                data={
                    "condition": top_condition.value,
                    "confidence": top_confidence,
                    "all_candidates": [
                        {"condition": c.value, "confidence": conf, "reasoning": r}
                        for c, conf, r in candidates
                    ],
                },
                next_actions=[TaskType.EVALUATE_ELIGIBILITY],
                rule_references=[f"Section {self._get_rule_section(top_condition)}"],
            )
        else:
            # Use LLM to disambiguate
            summary = self._format_dispute_summary(dispute)
            candidate_text = "\n".join(
                f"  {c.value} ({conf:.0%}): {r}" for c, conf, r in candidates
            )
            llm_analysis = await self._reason(
                f"Multiple dispute conditions are possible. Candidates:\n{candidate_text}\n\n"
                "Analyze the dispute facts and determine the BEST condition code. "
                "Explain your reasoning referencing specific Visa Rules.",
                context=summary,
            )

            dispute.condition = top_condition
            dispute.category = top_condition.category
            return TaskResult(
                success=True,
                decision=f"CONDITION_DETERMINED: {top_condition.value} (with LLM analysis)",
                reasoning=f"Rule engine candidates + LLM analysis:\n{llm_analysis}",
                data={
                    "condition": top_condition.value,
                    "confidence": top_confidence,
                    "llm_analysis": llm_analysis,
                },
                next_actions=[TaskType.EVALUATE_ELIGIBILITY],
                warnings=["Low confidence — recommend human review"],
            )

    async def _evaluate_eligibility(self, dispute: Dispute) -> TaskResult:
        """Evaluate dispute eligibility."""
        if dispute.condition is None:
            return TaskResult(
                success=False,
                decision="BLOCKED",
                reasoning="Cannot evaluate eligibility: dispute condition not yet determined",
                next_actions=[TaskType.DETERMINE_DISPUTE_CONDITION],
            )

        result = engine.evaluate_eligibility(dispute)

        if result.eligible:
            dispute.status = DisputeStatus.ELIGIBLE
            next_actions = [TaskType.CALCULATE_DISPUTE_AMOUNT, TaskType.FILE_DISPUTE]
            if result.wait_until and result.wait_until > date.today():
                next_actions = [TaskType.CALCULATE_DISPUTE_AMOUNT]
                dispute.status = DisputeStatus.PENDING_REVIEW
        else:
            dispute.status = DisputeStatus.INELIGIBLE
            next_actions = []

        return TaskResult(
            success=True,
            decision="ELIGIBLE" if result.eligible else "INELIGIBLE",
            reasoning="\n".join(
                result.reasons
                + [f"BLOCKING: {r}" for r in result.blocking_reasons]
                + [f"WARNING: {w}" for w in result.warnings]
            ),
            data={
                "eligible": result.eligible,
                "deadline": str(result.deadline) if result.deadline else None,
                "wait_until": str(result.wait_until) if result.wait_until else None,
                "blocking_reasons": result.blocking_reasons,
                "required_documentation": result.required_documentation,
            },
            next_actions=next_actions,
            rule_references=result.rule_references,
            warnings=result.warnings,
        )

    async def _validate_documentation(self, dispute: Dispute) -> TaskResult:
        """Validate that required documentation is present."""
        docs = engine.get_required_documentation(dispute)

        missing = []
        for doc in docs:
            if doc.startswith("[REQUIRED]"):
                doc_name = doc.replace("[REQUIRED] ", "")
                # Simplified check
                if not any(d.description == doc_name for d in dispute.evidence):
                    missing.append(doc_name)

        if missing:
            return TaskResult(
                success=True,
                decision="DOCUMENTATION_INCOMPLETE",
                reasoning=f"Missing {len(missing)} required document(s)",
                data={"missing_documents": missing, "all_required": docs},
                warnings=[f"Missing: {doc}" for doc in missing],
            )

        return TaskResult(
            success=True,
            decision="DOCUMENTATION_COMPLETE",
            reasoning="All required documentation is present",
            data={"all_required": docs},
        )

    def _get_rule_section(self, condition: DisputeCondition) -> str:
        from src.rules.registry import get_condition_rule
        return get_condition_rule(condition).rule_section
