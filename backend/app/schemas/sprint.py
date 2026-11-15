"""Pydantic schemas for sprint operations."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SprintStatus = Literal["planning", "active", "completed", "cancelled"]


class SprintCreate(BaseModel):
    """Schema for creating a new sprint."""

    name: str = Field(..., min_length=1, max_length=100)
    goal: str | None = None
    start_date: date
    # Omitted -> defaults to a two-week sprint (start + 13 days, inclusive).
    end_date: date | None = None
    capacity_hours: int = Field(default=0, ge=0)
    capacity_breakdown: dict[str, int] | None = None  # {member_id: hours}


class SprintUpdate(BaseModel):
    """Schema for updating a sprint (partial update)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: SprintStatus | None = None
    capacity_hours: int | None = Field(default=None, ge=0)
    capacity_breakdown: dict[str, int] | None = None
    velocity: int | None = None
    retrospective_notes: str | None = None


class SprintResponse(BaseModel):
    """Schema for sprint response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    goal: str | None
    start_date: date
    end_date: date
    status: str
    stream_id: UUID | None = None
    capacity_hours: int
    capacity_breakdown: dict[str, int] | None
    velocity: int | None
    retrospective_notes: str | None
    created_at: datetime
    updated_at: datetime | None


class SprintListResponse(BaseModel):
    """Schema for listing sprints."""

    sprints: list[SprintResponse]
    total: int


class SprintWithStats(SprintResponse):
    """Sprint response with computed statistics."""

    total_tasks: int = 0
    completed_tasks: int = 0
    total_story_points: int = 0
    completed_story_points: int = 0
    progress_percentage: float = 0.0


class TaskToSprintRequest(BaseModel):
    """Request to add/remove tasks from a sprint."""

    task_ids: list[UUID]


class BurndownDataPoint(BaseModel):
    """Single data point for a burndown chart.

    ``remaining_points`` is None on any day with no reading — a future date, or
    a past day whose confidence snapshot never ran. Consumers MUST break the
    line there. Rendering a gap as 0 claims the sprint finished that day.
    """

    date: date
    remaining_points: int | None = None
    ideal_points: float
    # "snapshot" = replayed from a stored end-of-day reading;
    # "live" = computed from current task state (today only);
    # None = no reading for this day.
    source: str | None = None


class SprintBurndown(BaseModel):
    """Burndown chart data for a sprint."""

    sprint_id: UUID
    sprint_name: str
    total_points: int
    # "pts" when the team estimates in story points, else "items".
    unit: str = "pts"
    data_points: list[BurndownDataPoint]
