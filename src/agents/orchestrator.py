"""The Brain — Central orchestration agent that routes dispute tasks to specialized sub-agents.

This is the core of the system. It:
1. Receives dispute tasks from the queue
2. Routes them to the appropriate sub-agent based on task type
3. Manages the end-to-end lifecycle of each dispute
4. Handles errors, retries, and escalation
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.agents.base import BaseAgent
from src.agents.escalation import EscalationAgent
from src.agents.intake import IntakeAgent
from src.agents.investigation import InvestigationAgent
from src.agents.resolution import ResolutionAgent
from src.config import AppConfig
from src.llm.base import LLMProvider
from src.models.dispute import Dispute
from src.models.enums import TaskStatus, TaskType
from src.models.task import DisputeTask, TaskResult
from src.queue.base import TaskQueue

logger = logging.getLogger(__name__)

# Map task types to the agent that handles them
TASK_ROUTING: dict[TaskType, str] = {
    TaskType.EVALUATE_ELIGIBILITY: "intake",
    TaskType.VALIDATE_DOCUMENTATION: "intake",
    TaskType.DETERMINE_DISPUTE_CONDITION: "intake",
    TaskType.CHECK_INVALID_CONDITIONS: "investigation",
    TaskType.REVIEW_COMPELLING_EVIDENCE: "investigation",
    TaskType.CALCULATE_DISPUTE_AMOUNT: "investigation",
    TaskType.FILE_DISPUTE: "resolution",
    TaskType.EVALUATE_RESPONSE: "resolution",
    TaskType.PREPARE_PRE_ARBITRATION: "resolution",
    TaskType.EVALUATE_PRE_ARBITRATION: "resolution",
    TaskType.PREPARE_ARBITRATION: "escalation",
    TaskType.PREPARE_COMPLIANCE: "escalation",
    TaskType.CALCULATE_DEADLINE: "investigation",
}


class Orchestrator:
    """The Brain — orchestrates dispute processing across specialized agents."""

    def __init__(
        self,
        config: AppConfig,
        queue: TaskQueue,
        llm: LLMProvider,
    ) -> None:
        self._config = config
        self._queue = queue
        self._llm = llm
        self._disputes: dict[str, Dispute] = {}
        self._running = False
        self._agents: dict[str, BaseAgent] = {}
        self._task_results: dict[UUID, TaskResult] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        """Initialize specialized sub-agents."""
        self._agents = {
            "intake": IntakeAgent(self._llm, self._disputes),
            "investigation": InvestigationAgent(self._llm, self._disputes),
            "resolution": ResolutionAgent(self._llm, self._disputes),
            "escalation": EscalationAgent(self._llm, self._disputes),
        }

    # ── Public API ───────────────────────────────────────────────────────

    async def submit_dispute(self, dispute: Dispute) -> UUID:
        """Submit a new dispute for processing. Returns the initial task ID."""
        dispute_id = str(dispute.dispute_id)
        self._disputes[dispute_id] = dispute
        logger.info(f"Dispute {dispute_id} submitted for processing")

        # Create the initial intake task
        initial_task = DisputeTask(
            dispute_id=dispute.dispute_id,
            task_type=TaskType.DETERMINE_DISPUTE_CONDITION,
            priority=3,
            payload={"source": "new_submission"},
        )
        await self._queue.enqueue(initial_task)
        logger.info(f"Initial task {initial_task.task_id} queued for dispute {dispute_id}")

        return initial_task.task_id

    async def process_next(self) -> TaskResult | None:
        """Process the next task in the queue. Returns the result or None if queue is empty."""
        task = await self._queue.dequeue()
        if task is None:
            return None

        logger.info(f"Processing task {task.task_id} ({task.task_type}) for dispute {task.dispute_id}")
        result = await self._process_task(task)
        self._task_results[task.task_id] = result

        # Enqueue follow-up tasks
        if result.success and result.next_actions:
            await self._enqueue_follow_ups(task, result)

        return result

    async def run(self) -> None:
        """Run the orchestrator loop — continuously process tasks from the queue."""
        self._running = True
        logger.info("Orchestrator started")

        while self._running:
            pending = await self._queue.get_pending_count()
            if pending == 0:
                await asyncio.sleep(self._config.queue.poll_interval_seconds)
                continue

            # Process up to max_concurrent tasks
            tasks_to_process = min(pending, self._config.queue.max_concurrent_tasks)
            results = await asyncio.gather(
                *[self.process_next() for _ in range(tasks_to_process)],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task processing error: {result}")

    def stop(self) -> None:
        """Stop the orchestrator loop."""
        self._running = False
        logger.info("Orchestrator stopping")

    def get_dispute(self, dispute_id: str) -> Dispute | None:
        """Get a dispute by ID."""
        return self._disputes.get(dispute_id)

    def get_task_result(self, task_id: UUID) -> TaskResult | None:
        """Get the result of a completed task."""
        return self._task_results.get(task_id)

    async def get_dispute_status(self, dispute_id: str) -> dict[str, Any]:
        """Get the full status of a dispute including all task results."""
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return {"error": f"Dispute {dispute_id} not found"}

        tasks = await self._queue.get_tasks_for_dispute(dispute.dispute_id)

        return {
            "dispute_id": str(dispute.dispute_id),
            "status": dispute.status.value,
            "phase": dispute.phase.value,
            "category": dispute.category.value if dispute.category else None,
            "condition": dispute.condition.value if dispute.condition else None,
            "dispute_amount": str(dispute.dispute_amount) if dispute.dispute_amount else None,
            "actions_count": len(dispute.actions),
            "evidence_count": len(dispute.evidence),
            "tasks": [
                {
                    "task_id": str(t.task_id),
                    "type": t.task_type.value,
                    "status": t.status.value,
                    "result": self._task_results.get(t.task_id, None),
                }
                for t in tasks
            ],
        }

    # ── Private methods ──────────────────────────────────────────────────

    async def _process_task(self, task: DisputeTask) -> TaskResult:
        """Route a task to the appropriate agent and process it."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        await self._queue.update_task(task)

        agent_name = TASK_ROUTING.get(task.task_type)
        if agent_name is None:
            result = TaskResult(
                success=False,
                decision="ROUTING_ERROR",
                reasoning=f"No agent registered for task type: {task.task_type}",
            )
            task.status = TaskStatus.FAILED
            task.error = result.reasoning
        else:
            agent = self._agents[agent_name]
            try:
                result = await agent.process(task)
                task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                task.result = result
            except Exception as e:
                logger.exception(f"Agent {agent_name} failed on task {task.task_id}")
                result = TaskResult(
                    success=False,
                    decision="AGENT_ERROR",
                    reasoning=str(e),
                )
                task.status = TaskStatus.FAILED
                task.error = str(e)

                # Retry logic
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.QUEUED
                    await self._queue.enqueue(task)
                    logger.info(f"Task {task.task_id} requeued (retry {task.retry_count}/{task.max_retries})")

        task.completed_at = datetime.utcnow()
        await self._queue.update_task(task)

        logger.info(
            f"Task {task.task_id} ({task.task_type}) completed: "
            f"{result.decision} (success={result.success})"
        )
        return result

    async def _enqueue_follow_ups(self, parent_task: DisputeTask, result: TaskResult) -> None:
        """Create and enqueue follow-up tasks based on a completed task's result."""
        for action in result.next_actions:
            try:
                task_type = TaskType(action)
            except ValueError:
                logger.warning(f"Unknown follow-up task type: {action}")
                continue

            follow_up = DisputeTask(
                dispute_id=parent_task.dispute_id,
                task_type=task_type,
                priority=parent_task.priority,
                parent_task_id=parent_task.task_id,
                payload=result.data,
            )
            await self._queue.enqueue(follow_up)
            logger.info(f"Follow-up task {follow_up.task_id} ({task_type}) enqueued")
