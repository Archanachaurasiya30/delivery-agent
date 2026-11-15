"""Pydantic schemas for task operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Literal["backlog", "todo", "in_progress", "review", "done"] = "backlog"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    assignee_id: UUID | None = None
    sprint_id: UUID | None = None
    feature_id: UUID | None = None
    story_points: int | None = Field(None, ge=1, le=21)
    estimated_hours: int | None = Field(None, ge=0)
    technology: str | None = Field(None, max_length=50)
    priority_order: int = 0
    external_id: str | None = None


class TaskUpdate(BaseModel):
    """Schema for updating a task with partial data."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Literal["backlog", "todo", "in_progress", "review", "done"] | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    assignee_id: UUID | None = None
    sprint_id: UUID | None = None
    feature_id: UUID | None = None
    story_points: int | None = Field(None, ge=1, le=21)
    estimated_hours: int | None = Field(None, ge=0)
    technology: str | None = Field(None, max_length=50)
    priority_order: int | None = None
    external_id: str | None = None


class TaskResponse(BaseModel):
    """Schema for task response."""

    id: UUID
    title: str
    description: str | None
    acceptance_criteria: str | None = None
    status: str
    priority: str
    assignee_id: UUID | None
    sprint_id: UUID | None
    feature_id: UUID | None = None
    story_points: int | None
    estimated_hours: int | None = None
    technology: str | None = None
    # Azure DevOps sub-area ("Storefront", "Smart Assistant", "Pulse"); NULL for
    # items filed on the stream root.
    project_name: str | None = None
    # "Bug", "Issue", "Task", "Product Backlog Item", "Feature", ...
    work_item_type: str | None = None
    priority_order: int
    external_id: str | None
    source: str = "local"
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """Schema for paginated task list response."""

    tasks: list[TaskResponse]
    total: int


class TaskStatusCount(BaseModel):
    """Schema for status count in summary."""

    status: str
    count: int


class TaskSummary(BaseModel):
    """Schema for task summary with counts by status and priority."""

    total: int
    by_status: list[TaskStatusCount]
    by_priority: dict[str, int]
