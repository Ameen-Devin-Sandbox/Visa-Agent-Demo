"""Tests for the task queue."""

import pytest

from src.models.enums import TaskPriority
from src.models.task import DisputeTask
from src.queue.task_queue import DisputeTaskQueue


@pytest.fixture
def queue() -> DisputeTaskQueue:
    return DisputeTaskQueue()


class TestDisputeTaskQueue:
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, queue: DisputeTaskQueue) -> None:
        task = DisputeTask(case_id="case-001", action="process_dispute")
        await queue.enqueue(task)
        assert not queue.is_empty

        dequeued = await queue.dequeue()
        assert dequeued is not None
        assert dequeued.case_id == "case-001"

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue: DisputeTaskQueue) -> None:
        low = DisputeTask(case_id="low", action="process", priority=TaskPriority.LOW)
        high = DisputeTask(case_id="high", action="process", priority=TaskPriority.HIGH)
        medium = DisputeTask(case_id="medium", action="process", priority=TaskPriority.MEDIUM)

        await queue.enqueue(low)
        await queue.enqueue(medium)
        await queue.enqueue(high)

        first = await queue.dequeue()
        assert first is not None
        assert first.case_id == "high"

        second = await queue.dequeue()
        assert second is not None
        assert second.case_id == "medium"

        third = await queue.dequeue()
        assert third is not None
        assert third.case_id == "low"

    @pytest.mark.asyncio
    async def test_empty_dequeue(self, queue: DisputeTaskQueue) -> None:
        result = await queue.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_complete_task(self, queue: DisputeTaskQueue) -> None:
        task = DisputeTask(case_id="case-001", action="process")
        await queue.enqueue(task)
        dequeued = await queue.dequeue()
        assert dequeued is not None

        await queue.complete_task(dequeued.task_id, {"status": "done"})
        stats = queue.get_stats()
        assert stats["completed"] == 1

    @pytest.mark.asyncio
    async def test_fail_task_retry(self, queue: DisputeTaskQueue) -> None:
        task = DisputeTask(case_id="case-001", action="process")
        await queue.enqueue(task)
        dequeued = await queue.dequeue()
        assert dequeued is not None

        await queue.fail_task(dequeued.task_id, "test error")
        stats = queue.get_stats()
        assert stats["failed"] == 1
        # Should be retried (re-enqueued)
        assert stats["retried"] == 1

    @pytest.mark.asyncio
    async def test_queue_depth(self, queue: DisputeTaskQueue) -> None:
        for i in range(3):
            task = DisputeTask(case_id=f"case-{i}", action="process")
            await queue.enqueue(task)

        assert queue.total_pending == 3
        depth = queue.get_queue_depth()
        assert depth["MEDIUM"] == 3

    @pytest.mark.asyncio
    async def test_get_task(self, queue: DisputeTaskQueue) -> None:
        task = DisputeTask(case_id="case-001", action="process")
        await queue.enqueue(task)
        found = queue.get_task(task.task_id)
        assert found is not None
        assert found.case_id == "case-001"
