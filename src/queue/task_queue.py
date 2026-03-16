"""Async task queue for dispute processing.

Provides a priority-based async queue with retry logic, dead letter queue,
and task lifecycle management.
"""

import asyncio
import logging
from collections import defaultdict

from src.models.enums import TaskPriority, TaskStatus
from src.models.task import DisputeTask

logger = logging.getLogger(__name__)


class DisputeTaskQueue:
    """Priority-based async task queue for dispute processing.

    Features:
    - Priority-based ordering (CRITICAL > HIGH > MEDIUM > LOW)
    - Automatic retry with configurable backoff
    - Dead letter queue for permanently failed tasks
    - Task status tracking and metrics
    """

    def __init__(self, max_queue_size: int = 10000) -> None:
        self._queues: dict[TaskPriority, asyncio.Queue[DisputeTask]] = {
            priority: asyncio.Queue(maxsize=max_queue_size) for priority in TaskPriority
        }
        self._active_tasks: dict[str, DisputeTask] = {}
        self._completed_tasks: dict[str, DisputeTask] = {}
        self._dead_letter: dict[str, DisputeTask] = {}
        self._task_index: dict[str, DisputeTask] = {}
        self._stats: dict[str, int] = defaultdict(int)
        self._running = False

    async def enqueue(self, task: DisputeTask) -> str:
        """Add a task to the queue.

        Args:
            task: The dispute task to enqueue.

        Returns:
            The task ID.
        """
        queue = self._queues[task.priority]
        await queue.put(task)
        self._task_index[task.task_id] = task
        self._stats["enqueued"] += 1
        logger.info(
            "Task enqueued: %s (priority=%s, case=%s, action=%s)",
            task.task_id,
            task.priority.name,
            task.case_id,
            task.action,
        )
        return task.task_id

    async def dequeue(self) -> DisputeTask | None:
        """Get the highest-priority task from the queue.

        Returns tasks in priority order: CRITICAL > HIGH > MEDIUM > LOW.

        Returns:
            The next task to process, or None if all queues are empty.
        """
        for priority in TaskPriority:
            queue = self._queues[priority]
            if not queue.empty():
                task = await queue.get()
                self._active_tasks[task.task_id] = task
                self._stats["dequeued"] += 1
                logger.info(
                    "Task dequeued: %s (priority=%s)",
                    task.task_id,
                    priority.name,
                )
                return task
        return None

    async def complete_task(self, task_id: str, result: dict[str, object]) -> None:
        """Mark a task as completed."""
        task = self._active_tasks.pop(task_id, None)
        if task is None:
            logger.warning("Attempted to complete unknown task: %s", task_id)
            return

        task.mark_completed(result)
        self._completed_tasks[task_id] = task
        self._stats["completed"] += 1
        logger.info("Task completed: %s", task_id)

    async def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed and handle retry logic."""
        task = self._active_tasks.pop(task_id, None)
        if task is None:
            logger.warning("Attempted to fail unknown task: %s", task_id)
            return

        task.mark_failed(error)
        self._stats["failed"] += 1

        if task.status == TaskStatus.RETRY:
            # Re-enqueue for retry
            await self.enqueue(task)
            self._stats["retried"] += 1
            logger.info(
                "Task requeued for retry: %s (attempt %d/%d)",
                task_id,
                task.retry_count,
                task.max_retries,
            )
        elif task.status == TaskStatus.DEAD_LETTER:
            self._dead_letter[task_id] = task
            self._stats["dead_letter"] += 1
            logger.warning(
                "Task moved to dead letter queue: %s (error: %s)",
                task_id,
                error,
            )

    def get_task(self, task_id: str) -> DisputeTask | None:
        """Get a task by ID from any state."""
        return self._task_index.get(task_id)

    def get_queue_depth(self) -> dict[str, int]:
        """Get the current depth of each priority queue."""
        return {priority.name: queue.qsize() for priority, queue in self._queues.items()}

    def get_stats(self) -> dict[str, int]:
        """Get queue processing statistics."""
        return {
            **dict(self._stats),
            "active": len(self._active_tasks),
            "dead_letter": len(self._dead_letter),
            "total_queued": sum(q.qsize() for q in self._queues.values()),
        }

    def get_dead_letter_tasks(self) -> list[DisputeTask]:
        """Get all tasks in the dead letter queue."""
        return list(self._dead_letter.values())

    @property
    def is_empty(self) -> bool:
        """Check if all queues are empty."""
        return all(q.empty() for q in self._queues.values())

    @property
    def total_pending(self) -> int:
        """Get total number of pending tasks across all priorities."""
        return sum(q.qsize() for q in self._queues.values())
