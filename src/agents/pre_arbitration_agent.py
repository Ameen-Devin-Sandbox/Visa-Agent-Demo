"""AI-powered pre-arbitration and arbitration processing agent.

Uses OpenAI to reason over Visa Core Rules Sections 11.2, 11.5, and 11.11
to evaluate pre-arbitration attempts, responses, and arbitration filings.
"""

from typing import Any

from src.agents.base_agent import BaseDisputeAgent
from src.llm.openai_client import chat_json
from src.llm.visa_rules import get_arbitration_rules, get_compelling_evidence_rules
from src.models.dispute import DisputeCase, RuleEvaluationResult
from src.models.enums import (
    AgentType,
    DisputeLifecycleStage,
    DisputeResolution,
)

_PRE_ARB_SYSTEM_PROMPT = (
    "You are a specialized Visa pre-arbitration and arbitration agent. You evaluate "
    "pre-arbitration attempts and responses according to Visa Core Rules Sections "
    "11.2, 11.5, and 11.11.\n\n"
    "Your evaluation must consider:\n"
    "1. Whether compelling evidence has been provided (per Section 11.5.2)\n"
    "2. Whether the pre-arbitration/arbitration is timely\n"
    "3. Whether the acquirer has valid grounds for pre-arbitration\n"
    "4. Whether the issuer's response is adequate\n"
    "5. Whether escalation to arbitration is warranted\n\n"
    "For PRE-ARBITRATION attempts, evaluate:\n"
    "- Has the acquirer provided compelling evidence?\n"
    "- Has a credit/reversal not been addressed?\n"
    "- Is there evidence the dispute is invalid?\n"
    "- Has the cardholder withdrawn the dispute?\n\n"
    "For PRE-ARBITRATION RESPONSES, evaluate:\n"
    "- Has the issuer accepted financial responsibility?\n"
    "- Has the issuer declined with valid certification?\n"
    "- Should the case proceed to arbitration?\n\n"
    "For ARBITRATION filings, evaluate:\n"
    "- Has the pre-arbitration cycle been completed?\n"
    "- Are there valid grounds for arbitration?\n\n"
    'You MUST respond with valid JSON in this exact format:\n'
    '{\n'
    '    "has_compelling_evidence": true/false,\n'
    '    "resolution": "<one of: issuer_win, acquirer_win, withdrawn, escalated_arbitration>",\n'
    '    "confidence": <float 0.0-1.0>,\n'
    '    "rationale": "<detailed explanation citing specific Visa rules sections>",\n'
    '    "rule_citations": [\n'
    '        {\n'
    '            "rule_section": "<e.g. 11.5.2>",\n'
    '            "rule_description": "<what the rule says>",\n'
    '            "is_satisfied": true/false,\n'
    '            "details": "<how this rule applies to this case>"\n'
    '        }\n'
    '    ],\n'
    '    "next_action": "<one of: resolved, awaiting_issuer_response, awaiting_acquirer_response, escalate_arbitration, human_review>",\n'
    '    "requires_human_review": true/false,\n'
    '    "human_review_reason": "<reason if human review needed, null otherwise>"\n'
    '}\n'
)


class PreArbitrationAgent(BaseDisputeAgent):
    """AI-powered agent handling pre-arbitration and arbitration stages.

    Uses OpenAI to reason over Visa Core Rules to evaluate compelling
    evidence, pre-arbitration grounds, and arbitration filings.
    """

    def __init__(self) -> None:
        super().__init__(AgentType.PRE_ARBITRATION)

    async def validate(self, case: DisputeCase) -> bool:
        """This agent handles cases in pre-arbitration or arbitration stages."""
        return case.stage in (
            DisputeLifecycleStage.PRE_ARBITRATION,
            DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
            DisputeLifecycleStage.ARBITRATION,
        )

    async def process(self, case: DisputeCase) -> DisputeCase:
        """Process a pre-arbitration or arbitration action using AI reasoning."""
        self.logger.info(
            "Processing pre-arbitration via AI: case=%s stage=%s",
            case.case_id,
            case.stage.value,
        )
        case.assigned_agent = self.agent_type.value

        if case.stage == DisputeLifecycleStage.PRE_ARBITRATION:
            return await self._process_pre_arbitration(case)
        elif case.stage == DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE:
            return await self._process_pre_arbitration_response(case)
        elif case.stage == DisputeLifecycleStage.ARBITRATION:
            return await self._process_arbitration(case)

        return case

    async def _process_pre_arbitration(self, case: DisputeCase) -> DisputeCase:
        """Process a pre-arbitration attempt using AI evaluation."""
        case.pre_arbitration_attempts += 1
        case.add_processing_note(
            f"Pre-arbitration attempt #{case.pre_arbitration_attempts} being evaluated by AI"
        )

        rules_context = (
            get_compelling_evidence_rules() + "\n\n---\n\n" + get_arbitration_rules()
        )

        result = self._evaluate_pre_arb_with_llm(case, rules_context)
        return self._apply_pre_arb_result(case, result, "prearb")

    async def _process_pre_arbitration_response(self, case: DisputeCase) -> DisputeCase:
        """Process the issuer response to a pre-arbitration attempt using AI."""
        case.add_processing_note("AI evaluating pre-arbitration response")

        rules_context = (
            get_compelling_evidence_rules() + "\n\n---\n\n" + get_arbitration_rules()
        )

        result = self._evaluate_pre_arb_with_llm(case, rules_context)
        return self._apply_pre_arb_result(case, result, "prearb_resp")

    async def _process_arbitration(self, case: DisputeCase) -> DisputeCase:
        """Process an arbitration filing using AI evaluation."""
        case.arbitration_filed = True
        case.add_processing_note(
            "AI evaluating arbitration case - escalating to Visa committee"
        )

        rules_context = get_arbitration_rules()
        result = self._evaluate_pre_arb_with_llm(case, rules_context)

        all_evaluations: list[RuleEvaluationResult] = []
        for citation in result.get("rule_citations", []):
            section = citation["rule_section"]
            eval_result = RuleEvaluationResult(
                rule_id="ai_arb_{}".format(section.replace(".", "_")),
                rule_section=section,
                rule_description=citation["rule_description"],
                is_satisfied=citation["is_satisfied"],
                details=citation["details"],
            )
            all_evaluations.append(eval_result)
            case.add_rule_evaluation(eval_result)

        rationale = result["rationale"]
        case.decision = self.create_decision(
            resolution=DisputeResolution.ESCALATED_ARBITRATION,
            rationale=f"[AI] {rationale}",
            rule_evaluations=all_evaluations,
            confidence=float(result.get("confidence", 0.70)),
            requires_human_review=True,
            human_review_reason="Arbitration requires Visa committee review",
        )
        case.advance_stage(
            DisputeLifecycleStage.HUMAN_REVIEW, "Escalated to Visa arbitration"
        )

        return case

    def _apply_pre_arb_result(
        self, case: DisputeCase, result: dict[str, Any], prefix: str
    ) -> DisputeCase:
        """Apply the LLM evaluation result to the case."""
        all_evaluations: list[RuleEvaluationResult] = []
        for citation in result.get("rule_citations", []):
            section = citation["rule_section"]
            eval_result = RuleEvaluationResult(
                rule_id="ai_{}_{}".format(prefix, section.replace(".", "_")),
                rule_section=section,
                rule_description=citation["rule_description"],
                is_satisfied=citation["is_satisfied"],
                details=citation["details"],
            )
            all_evaluations.append(eval_result)
            case.add_rule_evaluation(eval_result)

        next_action = result.get("next_action", "human_review")
        resolution_str = result.get("resolution", "issuer_win")
        confidence = float(result.get("confidence", 0.80))
        rationale = result["rationale"]

        if next_action == "resolved":
            resolution = DisputeResolution(resolution_str)
            case.decision = self.create_decision(
                resolution=resolution,
                rationale=f"[AI] {rationale}",
                rule_evaluations=all_evaluations,
                confidence=confidence,
            )
            case.advance_stage(
                DisputeLifecycleStage.RESOLVED,
                f"AI {prefix} resolved",
            )
        elif next_action == "awaiting_issuer_response":
            case.add_processing_note(f"[AI] {rationale}")
            case.advance_stage(
                DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
                "Awaiting issuer response to pre-arbitration",
            )
        elif next_action == "escalate_arbitration":
            case.decision = self.create_decision(
                resolution=DisputeResolution.ESCALATED_ARBITRATION,
                rationale=f"[AI] {rationale}",
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=True,
                human_review_reason="Arbitration filing decision required",
            )
            case.advance_stage(
                DisputeLifecycleStage.HUMAN_REVIEW, "Arbitration decision pending"
            )
        else:
            case.decision = self.create_decision(
                resolution=DisputeResolution(resolution_str),
                rationale=f"[AI] {rationale}",
                rule_evaluations=all_evaluations,
                confidence=confidence,
                requires_human_review=True,
                human_review_reason=result.get(
                    "human_review_reason", f"AI {prefix} review"
                ),
            )
            case.advance_stage(
                DisputeLifecycleStage.HUMAN_REVIEW, "AI escalated to human review"
            )

        return case

    def _evaluate_pre_arb_with_llm(
        self, case: DisputeCase, rules_context: str
    ) -> dict[str, Any]:
        """Use the LLM to evaluate a pre-arbitration/arbitration case."""
        if case.evidence:
            evidence_lines = [
                f"  - [{e.evidence_type}] {e.description} (provided by: {e.provided_by}, compelling: {e.is_compelling_evidence})"
                for e in case.evidence
            ]
            evidence_summary = "\n".join(evidence_lines)
        else:
            evidence_summary = "  No evidence provided"

        acquirer_evidence = [e for e in case.evidence if e.provided_by == "acquirer"]
        issuer_evidence = [e for e in case.evidence if e.provided_by == "issuer"]

        notes_text = "\n".join(case.processing_notes[-5:]) if case.processing_notes else "None"

        category_val = case.category.value if case.category else "Unknown"
        condition_val = case.condition.value if case.condition else "Unknown"
        statement = case.cardholder.cardholder_statement or "No statement"
        certification = case.issuer_certification or "None"

        user_prompt = (
            "Evaluate the following pre-arbitration/arbitration case.\n\n"
            "=== CASE DETAILS ===\n"
            f"Case ID: {case.case_id}\n"
            f"Current Stage: {case.stage.value}\n"
            f"Category: {category_val}\n"
            f"Condition: {condition_val}\n"
            f"Transaction Amount: {case.transaction.amount} {case.transaction.currency}\n"
            f"Merchant: {case.transaction.merchant_name}\n"
            f"Pre-Arbitration Attempts: {case.pre_arbitration_attempts}\n"
            f"Arbitration Filed: {case.arbitration_filed}\n"
            f"Issuer Certification: {certification}\n\n"
            f"Cardholder Statement: {statement}\n\n"
            f"All Evidence:\n{evidence_summary}\n\n"
            f"Acquirer Evidence Count: {len(acquirer_evidence)}\n"
            f"Issuer Evidence Count: {len(issuer_evidence)}\n\n"
            f"Processing Notes:\n{notes_text}\n\n"
            "=== VISA RULES REFERENCE ===\n"
            f"{rules_context}\n\n"
            "Evaluate this case and provide your analysis as JSON.\n"
        )
        return chat_json(_PRE_ARB_SYSTEM_PROMPT, user_prompt)
