"""Abstract task queue interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.models.task import DisputeTask


class TaskQueue(ABC):
    """Abstract interface for the dispute task queue."""

    @abstractmethod
    async def enqueue(self, task: DisputeTask) -> None:
        """Add a task to the queue."""
        ...

    @abstractmethod
    async def dequeue(self) -> DisputeTask | None:
        """Get the next task from the queue (highest priority first). Returns None if empty."""
        ...

    @abstractmethod
    async def peek(self) -> DisputeTask | None:
        """Look at the next task without removing it."""
        ...

    @abstractmethod
    async def get_task(self, task_id: UUID) -> DisputeTask | None:
        """Get a specific task by ID."""
        ...

    @abstractmethod
    async def update_task(self, task: DisputeTask) -> None:
        """Update a task in the queue."""
        ...

    @abstractmethod
    async def get_tasks_for_dispute(self, dispute_id: UUID) -> list[DisputeTask]:
        """Get all tasks for a specific dispute."""
        ...

    @abstractmethod
    async def size(self) -> int:
        """Get the number of tasks in the queue."""
        ...

    @abstractmethod
    async def get_pending_count(self) -> int:
        """Get the number of pending (queued) tasks."""
        ...
