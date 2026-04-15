"""The Brain - Central orchestration agent for dispute processing.

This is the core orchestrator that:
1. Picks tasks from the queue
2. Routes them to specialized sub-agents
3. Manages the end-to-end lifecycle of each dispute
4. Maintains audit trails and checkpoints
"""

import asyncio
import logging
from typing import Any

from src.agents.authorization_agent import AuthorizationDisputeAgent
from src.agents.base_agent import BaseDisputeAgent
from src.agents.consumer_disputes_agent import ConsumerDisputesAgent
from src.agents.fraud_agent import FraudDisputeAgent
from src.agents.pre_arbitration_agent import PreArbitrationAgent
from src.agents.processing_errors_agent import ProcessingErrorsAgent
from src.models.dispute import DisputeCase
from src.models.enums import (
    AgentType,
    DisputeCategory,
    DisputeLifecycleStage,
)
from src.models.task import DisputeTask
from src.queue.task_queue import DisputeTaskQueue
from src.rules.categorizer import categorize_dispute

logger = logging.getLogger(__name__)


class DisputeBrain:
    """Central orchestration agent for the Visa Disputes Processing system.

    The Brain is responsible for:
    - Consuming tasks from the priority queue
    - Categorizing incoming disputes using AI-powered categorization
    - Routing disputes to AI-powered specialized sub-agents
    - Managing lifecycle state transitions
    - Coordinating pre-arbitration and arbitration escalation
    - Maintaining a complete audit trail
    - Enforcing human-in-the-loop checkpoints

    Architecture:
        Queue -> Brain -> [AI Categorizer] -> AI Sub-Agent -> Decision -> Resolution
    """

    def __init__(self, task_queue: DisputeTaskQueue) -> None:
        self._queue = task_queue
        self._cases: dict[str, DisputeCase] = {}
        self._running = False
        self._worker_count = 3
        self._workers: list[asyncio.Task[None]] = []

        # Initialize sub-agents
        self._agents: dict[str, BaseDisputeAgent] = {
            AgentType.FRAUD.value: FraudDisputeAgent(),
            AgentType.AUTHORIZATION.value: AuthorizationDisputeAgent(),
            AgentType.PROCESSING_ERRORS.value: ProcessingErrorsAgent(),
            AgentType.CONSUMER_DISPUTES.value: ConsumerDisputesAgent(),
            AgentType.PRE_ARBITRATION.value: PreArbitrationAgent(),
        }

        # Category to agent mapping
        self._category_agent_map: dict[DisputeCategory, str] = {
            DisputeCategory.FRAUD: AgentType.FRAUD.value,
            DisputeCategory.AUTHORIZATION: AgentType.AUTHORIZATION.value,
            DisputeCategory.PROCESSING_ERRORS: AgentType.PROCESSING_ERRORS.value,
            DisputeCategory.CONSUMER_DISPUTES: AgentType.CONSUMER_DISPUTES.value,
        }

        logger.info("DisputeBrain initialized with %d sub-agents", len(self._agents))

    async def start(self) -> None:
        """Start the brain's worker loops to process tasks from the queue."""
        if self._running:
            logger.warning("Brain is already running")
            return

        self._running = True
        logger.info("Starting DisputeBrain with %d workers", self._worker_count)

        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)

    async def stop(self) -> None:
        """Stop the brain and all workers gracefully."""
        self._running = False
        logger.info("Stopping DisputeBrain...")

        for worker in self._workers:
            worker.cancel()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("DisputeBrain stopped")

    async def submit_dispute(self, case: DisputeCase) -> str:
        """Submit a new dispute case for processing.

        This is the main entry point for dispute intake. The case will be:
        1. Registered in the case store
        2. Enqueued as a task for processing

        Args:
            case: The dispute case to process.

        Returns:
            The case ID.
        """
        self._cases[case.case_id] = case
        case.advance_stage(DisputeLifecycleStage.INTAKE, "Dispute submitted to brain")
        logger.info("Dispute submitted: case=%s", case.case_id)

        task = DisputeTask(
            case_id=case.case_id,
            action="process_dispute",
        )
        await self._queue.enqueue(task)

        return case.case_id

    async def process_single(self, case: DisputeCase) -> DisputeCase:
        """Process a single dispute case synchronously (without the queue).

        Useful for testing and direct API calls.

        Args:
            case: The dispute case to process.

        Returns:
            The processed dispute case with decision.
        """
        self._cases[case.case_id] = case
        return await self._execute_dispute_processing(case)

    def get_case(self, case_id: str) -> DisputeCase | None:
        """Retrieve a dispute case by ID."""
        return self._cases.get(case_id)

    def get_all_cases(self) -> list[DisputeCase]:
        """Get all tracked dispute cases."""
        return list(self._cases.values())

    def get_case_summary(self, case_id: str) -> dict[str, Any] | None:
        """Get a summary of a dispute case."""
        case = self._cases.get(case_id)
        if case is None:
            return None

        return {
            "case_id": case.case_id,
            "stage": case.stage.value,
            "category": case.category.value if case.category else None,
            "condition": case.condition.value if case.condition else None,
            "resolution": case.decision.resolution.value if case.decision else None,
            "confidence": case.decision.confidence_score if case.decision else None,
            "requires_human_review": case.decision.requires_human_review if case.decision else None,
            "assigned_agent": case.assigned_agent,
            "rule_evaluations_count": len(case.rule_evaluations),
            "evidence_count": len(case.evidence),
            "processing_notes_count": len(case.processing_notes),
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        }

    async def escalate_to_pre_arbitration(self, case_id: str) -> DisputeCase | None:
        """Escalate a resolved dispute to pre-arbitration.

        This is used when the acquirer contests the initial dispute decision.
        """
        case = self._cases.get(case_id)
        if case is None:
            logger.warning("Cannot escalate: case %s not found", case_id)
            return None

        case.advance_stage(
            DisputeLifecycleStage.PRE_ARBITRATION,
            "Escalated to pre-arbitration",
        )
        case.decision = None  # Clear previous decision

        agent = self._agents[AgentType.PRE_ARBITRATION.value]
        return await agent.process(case)

    async def escalate_to_arbitration(self, case_id: str) -> DisputeCase | None:
        """Escalate a case to arbitration after pre-arbitration cycle."""
        case = self._cases.get(case_id)
        if case is None:
            logger.warning("Cannot escalate: case %s not found", case_id)
            return None

        case.advance_stage(
            DisputeLifecycleStage.ARBITRATION,
            "Escalated to arbitration",
        )
        case.decision = None

        agent = self._agents[AgentType.PRE_ARBITRATION.value]
        return await agent.process(case)

    async def approve_human_review(
        self,
        case_id: str,
        approved: bool,
        reviewer_notes: str = "",
    ) -> DisputeCase | None:
        """Process a human review decision.

        Args:
            case_id: The case to review.
            approved: Whether the human approves the system's decision.
            reviewer_notes: Optional notes from the reviewer.
        """
        case = self._cases.get(case_id)
        if case is None:
            return None

        if case.stage != DisputeLifecycleStage.HUMAN_REVIEW:
            logger.warning("Case %s is not in human review stage", case_id)
            return case

        case.add_processing_note(
            f"Human review: {'APPROVED' if approved else 'REJECTED'}. {reviewer_notes}"
        )

        if approved and case.decision:
            case.advance_stage(DisputeLifecycleStage.RESOLVED, "Approved by human reviewer")
        elif not approved:
            case.advance_stage(
                DisputeLifecycleStage.PROCESSING,
                f"Human reviewer rejected decision: {reviewer_notes}",
            )
            # Re-process with additional context
            case.decision = None

        return case

    # Internal methods

    async def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop that continuously processes tasks from the queue."""
        logger.info("Worker %s started", worker_id)

        while self._running:
            try:
                task = await self._queue.dequeue()
                if task is None:
                    await asyncio.sleep(0.5)
                    continue

                logger.info(
                    "Worker %s processing task %s (case=%s, action=%s)",
                    worker_id,
                    task.task_id,
                    task.case_id,
                    task.action,
                )

                try:
                    result = await self._handle_task(task)
                    await self._queue.complete_task(task.task_id, result)
                except Exception as e:
                    logger.exception("Task %s failed: %s", task.task_id, e)
                    await self._queue.fail_task(task.task_id, str(e))

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker %s encountered unexpected error", worker_id)
                await asyncio.sleep(1)

        logger.info("Worker %s stopped", worker_id)

    async def _handle_task(self, task: DisputeTask) -> dict[str, Any]:
        """Handle a single task from the queue."""
        case = self._cases.get(task.case_id)
        if case is None:
            raise ValueError(f"Case {task.case_id} not found")

        task.mark_in_progress(self.__class__.__name__)

        if task.action == "process_dispute":
            processed_case = await self._execute_dispute_processing(case)
            return {
                "case_id": processed_case.case_id,
                "stage": processed_case.stage.value,
                "resolution": processed_case.decision.resolution.value
                if processed_case.decision
                else None,
            }
        elif task.action == "pre_arbitration":
            result = await self.escalate_to_pre_arbitration(task.case_id)
            return {
                "case_id": task.case_id,
                "action": "pre_arbitration",
                "completed": result is not None,
            }
        elif task.action == "arbitration":
            result = await self.escalate_to_arbitration(task.case_id)
            return {
                "case_id": task.case_id,
                "action": "arbitration",
                "completed": result is not None,
            }
        else:
            raise ValueError(f"Unknown task action: {task.action}")

    async def _execute_dispute_processing(self, case: DisputeCase) -> DisputeCase:
        """Execute the full dispute processing pipeline.

        Pipeline:
        1. Validation (basic data checks)
        2. Categorization (determine category and condition)
        3. Agent routing and processing
        """
        # Stage 1: Validation
        case.advance_stage(DisputeLifecycleStage.VALIDATION, "Validating dispute data")
        validation_errors = self._validate_case(case)
        if validation_errors:
            case.add_processing_note(f"Validation errors: {validation_errors}")
            case.advance_stage(
                DisputeLifecycleStage.REJECTED, f"Validation failed: {validation_errors}"
            )
            return case

        # Stage 2: Categorization
        case.advance_stage(DisputeLifecycleStage.CATEGORIZATION, "Categorizing dispute")
        categorization = categorize_dispute(case)

        case.category = categorization.category
        case.condition = categorization.condition
        case.add_processing_note(
            f"Categorized as {categorization.category.value} / {categorization.condition.value} "
            f"(confidence: {categorization.confidence:.2f}): {categorization.rationale}"
        )

        if categorization.alternative_conditions:
            case.add_processing_note(
                f"Alternative conditions: {[c.value for c in categorization.alternative_conditions]}"
            )

        # Set dispute amount and currency if not already set
        if case.dispute_amount is None:
            case.dispute_amount = case.transaction.amount
        if case.dispute_currency is None:
            case.dispute_currency = case.transaction.currency

        # Set filing date if not set
        if case.dispute_filed_date is None:
            case.dispute_filed_date = case.created_at

        # Stage 3: Route to sub-agent
        case.advance_stage(DisputeLifecycleStage.PROCESSING, "Routing to sub-agent")
        agent = self._get_agent_for_case(case)

        if agent is None:
            case.add_processing_note("No suitable agent found for this dispute")
            case.advance_stage(DisputeLifecycleStage.FAILED, "No agent available")
            return case

        can_handle = await agent.validate(case)
        if not can_handle:
            case.add_processing_note(f"Agent {agent.agent_type.value} cannot handle this case")
            case.advance_stage(DisputeLifecycleStage.FAILED, "Agent validation failed")
            return case

        # Process through the agent
        processed_case = await agent.process(case)

        logger.info(
            "Dispute processed: case=%s category=%s condition=%s stage=%s",
            processed_case.case_id,
            processed_case.category,
            processed_case.condition,
            processed_case.stage.value,
        )

        return processed_case

    def _validate_case(self, case: DisputeCase) -> list[str]:
        """Perform basic validation on the dispute case."""
        errors: list[str] = []

        if not case.transaction.transaction_id:
            errors.append("Missing transaction ID")

        if case.transaction.amount <= 0:
            errors.append("Transaction amount must be positive")

        if not case.cardholder.cardholder_name:
            errors.append("Missing cardholder name")

        if not case.cardholder.partial_payment_credential:
            errors.append("Missing payment credential")

        return errors

    def _get_agent_for_case(self, case: DisputeCase) -> BaseDisputeAgent | None:
        """Route a case to the appropriate sub-agent."""
        # Pre-arbitration/arbitration routing
        if case.stage in (
            DisputeLifecycleStage.PRE_ARBITRATION,
            DisputeLifecycleStage.PRE_ARBITRATION_RESPONSE,
            DisputeLifecycleStage.ARBITRATION,
        ):
            return self._agents.get(AgentType.PRE_ARBITRATION.value)

        # Category-based routing
        if case.category is not None:
            agent_key = self._category_agent_map.get(case.category)
            if agent_key:
                return self._agents.get(agent_key)

        return None
