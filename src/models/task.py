"""Task models for the dispute processing queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.enums import TaskStatus, TaskType


class DisputeTask(BaseModel):
    """A unit of work dispatched by the orchestrator."""

    task_id: UUID = Field(default_factory=uuid4)
    dispute_id: UUID
    task_type: TaskType
    priority: int = 5  # 1 = highest, 10 = lowest
    status: TaskStatus = TaskStatus.QUEUED
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_agent: str | None = None
    result: TaskResult | None = None
    retry_count: int = 0
    max_retries: int = 3
    error: str | None = None
    parent_task_id: UUID | None = None
    follow_up_tasks: list[TaskType] = Field(default_factory=list)


class TaskResult(BaseModel):
    """Result of a completed task."""

    success: bool
    decision: str  # The determination made
    reasoning: str  # Detailed reasoning
    data: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
    rule_references: list[str] = Field(default_factory=list)  # Section references
    warnings: list[str] = Field(default_factory=list)
