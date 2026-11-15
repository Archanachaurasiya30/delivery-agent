"""Pydantic models for the Todo API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    """Payload for creating a todo."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class TodoUpdate(BaseModel):
    """Partial update — only the provided fields change."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


class Todo(BaseModel):
    """A stored todo item."""

    id: int
    title: str
    description: str = ""
    completed: bool = False
    created_at: datetime
