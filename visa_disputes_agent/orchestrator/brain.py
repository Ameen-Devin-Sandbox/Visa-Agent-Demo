"""The Brain - Central orchestration agent for dispute processing."""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from visa_disputes_agent.agents.authorization_agent import AuthorizationDisputeAgent
from visa_disputes_agent.agents.base_agent import BaseDisputeAgent
from visa_disputes_agent.agents.consumer_agent import ConsumerDisputeAgent
from visa_disputes_agent.agents.fraud_agent import FraudDisputeAgent
from visa_disputes_agent.agents.processing_error_agent import ProcessingErrorAgent
from visa_disputes_agent.config.settings import Settings
from visa_disputes_agent.models.dispute import DisputeDecision, DisputeTask
from visa_disputes_agent.models.enums import (
    DecisionOutcome,
    DisputeCategory,
    DisputeTaskStatus,
)
from visa_disputes_agent.queue.task_queue import DisputeTaskQueue
from visa_disputes_agent.rules.engine import RulesEngine

logger = structlog.get_logger()


class DisputeBrain:
    """The Brain - Central orchestrator for autonomous dispute processing.

    This is the core of the system. It:
    1. Picks dispute tasks from the queue
    2. Routes them to the appropriate specialized sub-agent
    3. Manages the end-to-end lifecycle of each dispute
    4. Handles escalation, retries, and error recovery
    5. Stores decisions for retrieval

    The Brain replaces the human dispute processor by autonomously
    applying Visa Core Rules to incoming disputes.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        queue: DisputeTaskQueue | None = None,
        rules_engine: RulesEngine | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._queue = queue or DisputeTaskQueue(
            max_size=self._settings.queue_max_size,
            max_retries=self._settings.queue_max_retries,
        )
        self._rules = rules_engine or RulesEngine()
        self._agents: dict[DisputeCategory, BaseDisputeAgent] = self._initialize_agents()
        self._decisions: dict[UUID, DisputeDecision] = {}
        self._running = False
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent_tasks)

        logger.info(
            "brain_initialized",
            agents=list(self._agents.keys()),
            max_concurrent=self._settings.max_concurrent_tasks,
        )

    def _initialize_agents(self) -> dict[DisputeCategory, BaseDisputeAgent]:
        """Initialize all specialized sub-agents."""
        return {
            DisputeCategory.FRAUD: FraudDisputeAgent(self._rules),
            DisputeCategory.AUTHORIZATION: AuthorizationDisputeAgent(self._rules),
            DisputeCategory.PROCESSING_ERRORS: ProcessingErrorAgent(self._rules),
            DisputeCategory.CONSUMER_DISPUTES: ConsumerDisputeAgent(self._rules),
        }

    @property
    def queue(self) -> DisputeTaskQueue:
        """Access the task queue."""
        return self._queue

    @property
    def rules_engine(self) -> RulesEngine:
        """Access the rules engine."""
        return self._rules

    @property
    def is_running(self) -> bool:
        """Check if the brain is actively processing."""
        return self._running

    async def submit_dispute(self, task: DisputeTask) -> UUID:
        """Submit a new dispute task for processing.

        Returns the task ID for tracking.
        """
        await self._queue.enqueue(task)
        logger.info(
            "dispute_submitted",
            task_id=str(task.task_id),
            category=task.dispute_category.value if task.dispute_category else "unclassified",
            amount=str(task.dispute_amount),
        )
        return task.task_id

    async def process_single(self, task: DisputeTask) -> DisputeDecision:
        """Process a single dispute task synchronously.

        Useful for testing and direct API calls.
        """
        logger.info("processing_single_dispute", task_id=str(task.task_id))

        # Classify if needed
        if task.dispute_category is None:
            condition = self._rules.classify_dispute(task)
            if condition is not None:
                task.dispute_category = self._rules.get_category_for_condition(condition)
                task.dispute_condition = condition

        # Route to appropriate agent
        agent = self._route_to_agent(task)
        if agent is None:
            decision = DisputeDecision(
                task_id=task.task_id,
                outcome=DecisionOutcome.ESCALATE_TO_HUMAN,
                confidence_score=0.0,
                reasoning="Unable to determine dispute category for routing",
                escalation_reason="No applicable agent found",
            )
            self._decisions[task.task_id] = decision
            return decision

        # Process
        decision = await agent.process(task)
        self._decisions[task.task_id] = decision

        # Handle escalation thresholds
        decision = self._apply_confidence_thresholds(task, decision)

        logger.info(
            "dispute_processed",
            task_id=str(task.task_id),
            outcome=decision.outcome.value,
            confidence=decision.confidence_score,
            agent=agent.agent_name,
        )
        return decision

    async def start(self) -> None:
        """Start the brain's processing loop.

        Continuously polls the queue and processes disputes.
        """
        self._running = True
        logger.info("brain_started", poll_interval=self._settings.queue_poll_interval_seconds)

        try:
            async for task in self._queue.poll(self._settings.queue_poll_interval_seconds):
                if not self._running:
                    break
                asyncio.create_task(self._process_task_with_semaphore(task))
        except asyncio.CancelledError:
            logger.info("brain_stopping")
        finally:
            self._running = False
            logger.info("brain_stopped")

    async def stop(self) -> None:
        """Stop the brain's processing loop."""
        self._running = False
        logger.info("brain_stop_requested")

    async def _process_task_with_semaphore(self, task: DisputeTask) -> None:
        """Process a task with concurrency limiting."""
        async with self._semaphore:
            try:
                decision = await self.process_single(task)
                if decision.outcome in {
                    DecisionOutcome.DISPUTE_VALID,
                    DecisionOutcome.DISPUTE_INVALID,
                    DecisionOutcome.DISPUTE_PARTIALLY_VALID,
                }:
                    await self._queue.complete(task.task_id)
                elif decision.outcome == DecisionOutcome.ESCALATE_TO_HUMAN:
                    await self._queue.escalate(
                        task.task_id, decision.escalation_reason
                    )
                else:
                    # Non-final decisions - mark as complete but may need follow-up
                    await self._queue.complete(task.task_id)

            except Exception as e:
                logger.error(
                    "task_processing_failed",
                    task_id=str(task.task_id),
                    error=str(e),
                    exc_info=True,
                )
                await self._queue.fail(task.task_id, str(e))

    def _route_to_agent(self, task: DisputeTask) -> BaseDisputeAgent | None:
        """Route a task to the appropriate sub-agent based on category."""
        if task.dispute_category is not None:
            agent = self._agents.get(task.dispute_category)
            if agent is not None:
                logger.debug(
                    "task_routed",
                    task_id=str(task.task_id),
                    agent=agent.agent_name,
                    category=task.dispute_category.value,
                )
                return agent

        # Try to infer category from condition
        if task.dispute_condition is not None:
            try:
                category = self._rules.get_category_for_condition(task.dispute_condition)
                task.dispute_category = category
                return self._agents.get(category)
            except KeyError:
                pass

        logger.warning(
            "routing_failed",
            task_id=str(task.task_id),
            category=task.dispute_category,
        )
        return None

    def _apply_confidence_thresholds(
        self, task: DisputeTask, decision: DisputeDecision
    ) -> DisputeDecision:
        """Apply confidence thresholds to determine if human review is needed."""
        if not self._settings.enable_human_in_loop:
            return decision

        if decision.is_final() and decision.confidence_score < self._settings.human_review_threshold:
            logger.info(
                "low_confidence_escalation",
                task_id=str(task.task_id),
                confidence=decision.confidence_score,
                threshold=self._settings.human_review_threshold,
            )
            decision.outcome = DecisionOutcome.ESCALATE_TO_HUMAN
            decision.escalation_reason = (
                f"Confidence score {decision.confidence_score:.2f} is below "
                f"threshold {self._settings.human_review_threshold:.2f}"
            )
            decision.human_review_notes = (
                f"Original decision: {decision.reasoning}. "
                f"Escalated due to low confidence."
            )

        return decision

    def get_decision(self, task_id: UUID) -> DisputeDecision | None:
        """Retrieve the decision for a processed dispute."""
        return self._decisions.get(task_id)

    async def get_task_status(self, task_id: UUID) -> DisputeTaskStatus | None:
        """Get the current status of a task."""
        task = await self._queue.get_task(task_id)
        if task is not None:
            return task.status
        if task_id in self._decisions:
            return DisputeTaskStatus.COMPLETED
        return None

    def get_stats(self) -> dict[str, object]:
        """Get brain statistics including queue stats and decision counts."""
        decision_outcomes: dict[str, int] = {}
        for decision in self._decisions.values():
            outcome = decision.outcome.value
            decision_outcomes[outcome] = decision_outcomes.get(outcome, 0) + 1

        return {
            "queue": self._queue.get_stats(),
            "decisions": {
                "total": len(self._decisions),
                "by_outcome": decision_outcomes,
            },
            "is_running": self._running,
            "agents": [
                {"name": agent.agent_name, "category": cat.value}
                for cat, agent in self._agents.items()
            ],
        }
