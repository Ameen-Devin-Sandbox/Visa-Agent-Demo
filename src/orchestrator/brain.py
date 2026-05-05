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

        # TODO: Initialize all sub-agents in self._agents dict, keyed by AgentType.value:
        # - FRAUD -> FraudDisputeAgent()
        # - AUTHORIZATION -> AuthorizationDisputeAgent()
        # - PROCESSING_ERRORS -> ProcessingErrorsAgent()
        # - CONSUMER_DISPUTES -> ConsumerDisputesAgent()
        # - PRE_ARBITRATION -> PreArbitrationAgent()
        self._agents: dict[str, BaseDisputeAgent] = {}

        # TODO: Create self._category_agent_map mapping DisputeCategory -> agent key string
        # Maps each of the 4 categories to the corresponding agent type value
        self._category_agent_map: dict[DisputeCategory, str] = {}

        logger.info("DisputeBrain initialized with %d sub-agents", len(self._agents))

    async def start(self) -> None:
        """Start the brain's worker loops to process tasks from the queue."""
        if self._running:
            return
        self._running = True
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)

    async def stop(self) -> None:
        """Stop the brain and all workers gracefully."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def submit_dispute(self, case: DisputeCase) -> str:
        """Submit a new dispute case for processing via the queue.

        TODO: Implement:
        1. Store the case in self._cases
        2. Advance stage to INTAKE
        3. Create a DisputeTask with action="process_dispute"
        4. Enqueue the task
        5. Return the case_id
        """
        raise NotImplementedError("Module 4: Implement submit_dispute")

    async def process_single(self, case: DisputeCase) -> DisputeCase:
        """Process a single dispute case synchronously (without the queue).

        TODO: Store the case and call _execute_dispute_processing() directly.
        """
        raise NotImplementedError("Module 4: Implement process_single")

    def get_case(self, case_id: str) -> DisputeCase | None:
        """Retrieve a dispute case by ID."""
        return self._cases.get(case_id)

    def get_all_cases(self) -> list[DisputeCase]:
        """Get all tracked dispute cases."""
        return list(self._cases.values())

    def get_case_summary(self, case_id: str) -> dict[str, Any] | None:
        """Get a summary of a dispute case.

        TODO: Return a dict with: case_id, stage, category, condition, resolution,
        confidence, requires_human_review, assigned_agent, rule_evaluations_count,
        evidence_count, processing_notes_count, created_at, updated_at.
        Return None if case not found.
        """
        raise NotImplementedError("Module 4: Implement get_case_summary")

    async def escalate_to_pre_arbitration(self, case_id: str) -> DisputeCase | None:
        """Escalate a resolved dispute to pre-arbitration.

        TODO: Look up the case, advance to PRE_ARBITRATION stage,
        clear the previous decision, and run the PreArbitrationAgent.
        """
        raise NotImplementedError("Module 4: Implement escalate_to_pre_arbitration")

    async def escalate_to_arbitration(self, case_id: str) -> DisputeCase | None:
        """Escalate a case to arbitration after pre-arbitration cycle.

        TODO: Similar to escalate_to_pre_arbitration but advance to ARBITRATION.
        """
        raise NotImplementedError("Module 4: Implement escalate_to_arbitration")

    async def approve_human_review(
        self,
        case_id: str,
        approved: bool,
        reviewer_notes: str = "",
    ) -> DisputeCase | None:
        """Process a human review decision.

        TODO: Look up the case, verify it's in HUMAN_REVIEW stage.
        If approved -> advance to RESOLVED.
        If rejected -> advance to PROCESSING, clear decision.
        """
        raise NotImplementedError("Module 4: Implement approve_human_review")

    # Internal methods

    async def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop that continuously processes tasks from the queue.

        Workers wake instantly when a task is enqueued via the queue's
        internal ``asyncio.Event`` rather than polling on a fixed interval.
        """
        while self._running:
            try:
                task = await self._queue.dequeue()
                if task is None:
                    await self._queue.wait_for_task()
                    continue
                try:
                    result = await self._handle_task(task)
                    await self._queue.complete_task(task.task_id, result)
                except Exception as e:
                    logger.exception("Task %s failed: %s", task.task_id, e)
                    await self._queue.fail_task(task.task_id, str(e))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker %s error", worker_id)
                await asyncio.sleep(1)

    async def _handle_task(self, task: DisputeTask) -> dict[str, Any]:
        """Handle a single task from the queue.

        TODO: Look up the case, route based on task.action:
        - "process_dispute" -> _execute_dispute_processing()
        - "pre_arbitration" -> escalate_to_pre_arbitration()
        - "arbitration" -> escalate_to_arbitration()
        Return a result dict with case_id and outcome.
        """
        raise NotImplementedError("Module 4: Implement _handle_task")

    async def _execute_dispute_processing(self, case: DisputeCase) -> DisputeCase:
        """Execute the full dispute processing pipeline.

        TODO: Implement the 3-stage pipeline:
        Stage 1 - Validation:
          - Advance to VALIDATION, run _validate_case()
          - If errors, advance to REJECTED and return

        Stage 2 - Categorization:
          - Advance to CATEGORIZATION
          - Call ``await categorize_dispute(case)`` to get category + condition
          - Set case.category and case.condition
          - Set dispute_amount, dispute_currency, dispute_filed_date defaults

        Stage 3 - Agent Processing:
          - Advance to PROCESSING
          - Call _get_agent_for_case() to find the right agent
          - Validate the agent can handle the case
          - Call agent.process(case) and return the result
        """
        raise NotImplementedError("Module 4: Implement _execute_dispute_processing")

    def _validate_case(self, case: DisputeCase) -> list[str]:
        """Perform basic validation on the dispute case.

        TODO: Check for:
        - Missing transaction_id
        - Amount <= 0
        - Missing cardholder_name
        - Missing partial_payment_credential
        Return a list of error messages (empty if valid).
        """
        raise NotImplementedError("Module 4: Implement _validate_case")

    def _get_agent_for_case(self, case: DisputeCase) -> BaseDisputeAgent | None:
        """Route a case to the appropriate sub-agent.

        TODO: Route based on:
        1. If case is in pre-arb/arbitration stage -> PreArbitrationAgent
        2. Otherwise, use case.category to look up in _category_agent_map
        """
        raise NotImplementedError("Module 4: Implement _get_agent_for_case")
