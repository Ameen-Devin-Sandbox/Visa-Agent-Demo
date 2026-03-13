"""Tests for the task queue."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.enums import TaskStatus, TaskType
from src.models.task import DisputeTask
from src.queue.memory import InMemoryQueue


@pytest.fixture
def queue():
    return InMemoryQueue()


def make_task(priority: int = 5, task_type: TaskType = TaskType.EVALUATE_ELIGIBILITY) -> DisputeTask:
    return DisputeTask(
        dispute_id=uuid4(),
        task_type=task_type,
        priority=priority,
    )


class TestInMemoryQueue:
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, queue):
        task = make_task()
        await queue.enqueue(task)
        result = await queue.dequeue()
        assert result is not None
        assert result.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_dequeue_empty(self, queue):
        result = await queue.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        low = make_task(priority=10)
        high = make_task(priority=1)
        medium = make_task(priority=5)

        await queue.enqueue(low)
        await queue.enqueue(high)
        await queue.enqueue(medium)

        first = await queue.dequeue()
        second = await queue.dequeue()
        third = await queue.dequeue()

        assert first.task_id == high.task_id
        assert second.task_id == medium.task_id
        assert third.task_id == low.task_id

    @pytest.mark.asyncio
    async def test_size(self, queue):
        assert await queue.size() == 0
        await queue.enqueue(make_task())
        assert await queue.size() == 1
        await queue.enqueue(make_task())
        assert await queue.size() == 2

    @pytest.mark.asyncio
    async def test_pending_count(self, queue):
        task = make_task()
        await queue.enqueue(task)
        assert await queue.get_pending_count() == 1

        # Dequeue changes status implicitly (task is returned)
        await queue.dequeue()
        # After dequeue, the task is no longer QUEUED
        assert await queue.get_pending_count() == 0

    @pytest.mark.asyncio
    async def test_get_task(self, queue):
        task = make_task()
        await queue.enqueue(task)
        found = await queue.get_task(task.task_id)
        assert found is not None
        assert found.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_tasks_for_dispute(self, queue):
        dispute_id = uuid4()
        t1 = DisputeTask(dispute_id=dispute_id, task_type=TaskType.EVALUATE_ELIGIBILITY, priority=5)
        t2 = DisputeTask(dispute_id=dispute_id, task_type=TaskType.FILE_DISPUTE, priority=5)
        t3 = DisputeTask(dispute_id=uuid4(), task_type=TaskType.EVALUATE_ELIGIBILITY, priority=5)

        await queue.enqueue(t1)
        await queue.enqueue(t2)
        await queue.enqueue(t3)

        tasks = await queue.get_tasks_for_dispute(dispute_id)
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_update_task(self, queue):
        task = make_task()
        await queue.enqueue(task)
        task.status = TaskStatus.IN_PROGRESS
        await queue.update_task(task)
        updated = await queue.get_task(task.task_id)
        assert updated.status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_skips_non_queued_on_dequeue(self, queue):
        t1 = make_task(priority=1)
        t2 = make_task(priority=2)

        await queue.enqueue(t1)
        await queue.enqueue(t2)

        # Mark t1 as completed so it should be skipped
        t1.status = TaskStatus.COMPLETED
        await queue.update_task(t1)

        result = await queue.dequeue()
        assert result.task_id == t2.task_id
