"""Pydantic schemas for team management API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeamMemberCreate(BaseModel):
    """Schema for creating a new team member."""

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: Literal["developer", "tech_lead", "qa", "designer", "devops"] = "developer"
    capacity_hours_per_sprint: int = Field(default=60, ge=0, le=80)
    is_available: bool = True


class TeamMemberUpdate(BaseModel):
    """Schema for updating a team member (partial update)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    role: Literal["developer", "tech_lead", "qa", "designer", "devops"] | None = None
    capacity_hours_per_sprint: int | None = Field(default=None, ge=0, le=80)
    is_available: bool | None = None


class TeamMemberResponse(BaseModel):
    """Schema for team member response."""

    id: UUID
    name: str
    email: str
    role: str
    capacity_hours_per_sprint: int
    is_available: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TeamMemberListResponse(BaseModel):
    """Schema for list of team members response."""

    members: list[TeamMemberResponse]
    total: int
