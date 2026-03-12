"""Task queue for dispute processing - manages intake and distribution of dispute tasks."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

import structlog

from visa_disputes_agent.models.dispute import DisputeTask
from visa_disputes_agent.models.enums import DisputeTaskStatus, Priority

logger = structlog.get_logger()


class DisputeTaskQueue:
    """In-memory priority task queue for dispute processing.

    Provides an async interface matching production message queue patterns
    (Redis, RabbitMQ, etc.) for easy migration. Tasks are processed in
    priority order: CRITICAL > HIGH > MEDIUM > LOW.
    """

    PRIORITY_ORDER = {
        Priority.CRITICAL: 0,
        Priority.HIGH: 1,
        Priority.MEDIUM: 2,
        Priority.LOW: 3,
    }

    def __init__(self, max_size: int = 10000, max_retries: int = 3) -> None:
        self._queues: dict[Priority, asyncio.Queue[DisputeTask]] = {
            priority: asyncio.Queue(maxsize=max_size)
            for priority in Priority
        }
        self._in_progress: dict[UUID, DisputeTask] = {}
        self._completed: dict[UUID, DisputeTask] = {}
        self._failed: dict[UUID, DisputeTask] = {}
        self._dead_letter: list[DisputeTask] = []
        self._max_retries = max_retries
        self._stats: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        logger.info("task_queue_initialized", max_size=max_size, max_retries=max_retries)

    async def enqueue(self, task: DisputeTask) -> None:
        """Add a dispute task to the queue."""
        task.status = DisputeTaskStatus.PENDING
        task.updated_at = datetime.utcnow()

        queue = self._queues[task.priority]
        await queue.put(task)

        self._stats["total_enqueued"] += 1
        self._stats[f"enqueued_{task.priority.value}"] += 1

        logger.info(
            "task_enqueued",
            task_id=str(task.task_id),
            priority=task.priority.value,
            category=task.dispute_category.value if task.dispute_category else "unclassified",
        )

    async def dequeue(self) -> DisputeTask | None:
        """Get the next highest-priority task from the queue.

        Returns None if all queues are empty.
        """
        for priority in sorted(Priority, key=lambda p: self.PRIORITY_ORDER[p]):
            queue = self._queues[priority]
            if not queue.empty():
                task = queue.get_nowait()
                task.status = DisputeTaskStatus.IN_PROGRESS
                task.updated_at = datetime.utcnow()

                async with self._lock:
                    self._in_progress[task.task_id] = task

                self._stats["total_dequeued"] += 1
                logger.info(
                    "task_dequeued",
                    task_id=str(task.task_id),
                    priority=priority.value,
                )
                return task

        return None

    async def complete(self, task_id: UUID) -> None:
        """Mark a task as completed."""
        async with self._lock:
            task = self._in_progress.pop(task_id, None)
            if task is not None:
                task.status = DisputeTaskStatus.COMPLETED
                task.updated_at = datetime.utcnow()
                self._completed[task_id] = task
                self._stats["total_completed"] += 1
                logger.info("task_completed", task_id=str(task_id))

    async def fail(self, task_id: UUID, reason: str = "") -> None:
        """Mark a task as failed. Retries if under the retry limit."""
        async with self._lock:
            task = self._in_progress.pop(task_id, None)
            if task is None:
                return

            task.retry_count += 1
            task.add_log_entry("task_failed", f"Failure reason: {reason}")

            if task.retry_count < self._max_retries:
                # Re-enqueue for retry
                task.status = DisputeTaskStatus.PENDING
                task.updated_at = datetime.utcnow()
                await self._queues[task.priority].put(task)
                self._stats["total_retried"] += 1
                logger.warning(
                    "task_retrying",
                    task_id=str(task_id),
                    retry_count=task.retry_count,
                    reason=reason,
                )
            else:
                # Send to dead letter queue
                task.status = DisputeTaskStatus.FAILED
                task.updated_at = datetime.utcnow()
                self._failed[task_id] = task
                self._dead_letter.append(task)
                self._stats["total_failed"] += 1
                logger.error(
                    "task_dead_lettered",
                    task_id=str(task_id),
                    retry_count=task.retry_count,
                    reason=reason,
                )

    async def escalate(self, task_id: UUID, reason: str = "") -> None:
        """Escalate a task for human review."""
        async with self._lock:
            task = self._in_progress.pop(task_id, None)
            if task is not None:
                task.status = DisputeTaskStatus.ESCALATED
                task.updated_at = datetime.utcnow()
                task.add_log_entry("task_escalated", f"Escalation reason: {reason}")
                self._stats["total_escalated"] += 1
                logger.info(
                    "task_escalated",
                    task_id=str(task_id),
                    reason=reason,
                )

    async def get_task(self, task_id: UUID) -> DisputeTask | None:
        """Get a task by ID from any state."""
        async with self._lock:
            if task_id in self._in_progress:
                return self._in_progress[task_id]
            if task_id in self._completed:
                return self._completed[task_id]
            if task_id in self._failed:
                return self._failed[task_id]
        return None

    @property
    def pending_count(self) -> int:
        """Total number of pending tasks across all priority queues."""
        return sum(q.qsize() for q in self._queues.values())

    @property
    def in_progress_count(self) -> int:
        """Number of tasks currently being processed."""
        return len(self._in_progress)

    @property
    def completed_count(self) -> int:
        """Number of completed tasks."""
        return len(self._completed)

    @property
    def failed_count(self) -> int:
        """Number of failed tasks."""
        return len(self._failed)

    @property
    def dead_letter_count(self) -> int:
        """Number of tasks in the dead letter queue."""
        return len(self._dead_letter)

    def get_stats(self) -> dict[str, int]:
        """Get queue statistics."""
        return {
            **dict(self._stats),
            "pending": self.pending_count,
            "in_progress": self.in_progress_count,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "dead_letter": self.dead_letter_count,
        }

    async def poll(self, interval: float = 1.0) -> AsyncIterator[DisputeTask]:
        """Continuously poll the queue for tasks.

        Yields tasks as they become available.
        """
        while True:
            task = await self.dequeue()
            if task is not None:
                yield task
            else:
                await asyncio.sleep(interval)
