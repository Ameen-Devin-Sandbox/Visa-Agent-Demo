"""In-memory task queue implementation for development/demo."""

from __future__ import annotations

import asyncio
import heapq
from uuid import UUID

from src.models.enums import TaskStatus
from src.models.task import DisputeTask
from src.queue.base import TaskQueue


class InMemoryQueue(TaskQueue):
    """In-memory priority queue backed by a heap.

    Priority is (priority_value, creation_time) so higher priority (lower number)
    and earlier creation time are dequeued first.
    """

    def __init__(self) -> None:
        self._heap: list[tuple[int, float, DisputeTask]] = []
        self._tasks: dict[UUID, DisputeTask] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, task: DisputeTask) -> None:
        async with self._lock:
            entry = (task.priority, task.created_at.timestamp(), task)
            heapq.heappush(self._heap, entry)
            self._tasks[task.task_id] = task

    async def dequeue(self) -> DisputeTask | None:
        async with self._lock:
            while self._heap:
                priority, ts, task = heapq.heappop(self._heap)
                if task.status == TaskStatus.QUEUED:
                    task.status = TaskStatus.IN_PROGRESS
                    return task
            return None

    async def peek(self) -> DisputeTask | None:
        async with self._lock:
            for _, _, task in self._heap:
                if task.status == TaskStatus.QUEUED:
                    return task
            return None

    async def get_task(self, task_id: UUID) -> DisputeTask | None:
        return self._tasks.get(task_id)

    async def update_task(self, task: DisputeTask) -> None:
        async with self._lock:
            self._tasks[task.task_id] = task

    async def get_tasks_for_dispute(self, dispute_id: UUID) -> list[DisputeTask]:
        return [t for t in self._tasks.values() if t.dispute_id == dispute_id]

    async def size(self) -> int:
        return len(self._tasks)

    async def get_pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)
