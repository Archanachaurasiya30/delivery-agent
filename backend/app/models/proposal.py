"""Proposal model for AI-generated delivery proposals."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseMixin


class Proposal(Base, BaseMixin):
    """
    Proposal model for AI-generated delivery recommendations.

    Represents proposals created by the AI agent for sprint planning,
    task allocation, and other delivery decisions.

    State machine:
        draft -> pending_review -> approved -> executed
                               -> rejected
        executed -> failed (on execution error)

    Attributes:
        type: Proposal type (e.g., sprint_planning, task_assignment, blocker_resolution)
        state: Current state in the approval workflow
        content: Structured JSON content of the proposal
        reasoning: AI explanation for the proposal
        confidence: AI confidence level (low, medium, high)
        created_by_agent: Identifier of the agent that created this
        reviewed_by: Username of reviewer (if reviewed)
        reviewed_at: Timestamp of review
        prompt_log: Debug log of prompts sent to LLM
        execution_result: Result of executing the approved proposal
    """

    __tablename__ = "proposals"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # Altitude of the decision. "project" = operational (a PM's queue);
    # "stream"/"portfolio" surface only at the portfolio level. ``escalated``
    # forces a decision up regardless of scope. A cross-stream proposal carries
    # stream_id=None and scope in {stream, portfolio}.
    scope: Mapped[str] = mapped_column(String(20), default="project", nullable=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stream_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("streams.id"),
        nullable=True,
    )
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_by_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    prompt_log: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
