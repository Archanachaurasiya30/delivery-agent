"""Pydantic schemas for feature operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeatureCreate(BaseModel):
    """Schema for creating a new feature."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    stream_id: UUID | None = None


class FeatureResponse(BaseModel):
    """Schema for feature response."""

    id: UUID
    name: str
    description: str | None
    stream_id: UUID | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FeatureListResponse(BaseModel):
    """Schema for the feature list response."""

    features: list[FeatureResponse]
    total: int
