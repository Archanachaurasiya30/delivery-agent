"""Standup models: a round of collection and per-member entries."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    pass


class StandupRound(Base, BaseMixin):
    """
    A single standup collection round.

    State machine:
        collecting -> closed -> analyzed
                            -> failed (on analysis error)

    Attributes:
        status: Lifecycle state of the round.
        trigger: How the round started ("manual" | "scheduled").
        scheduled_for: The day this round is for (scheduled runs).
        expected_count: Number of members we asked (linked + available).
        proposal_id: The Proposal produced when the round is analyzed.
        summary: Parsed AI report (blockers/risks/recommendations/summary).
        closed_at: When collection was closed.
    """

    __tablename__ = "standup_rounds"

    status: Mapped[str] = mapped_column(String(20), default="collecting", nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proposal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("proposals.id"), nullable=True
    )
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    entries: Mapped[list["StandupEntry"]] = relationship(
        "StandupEntry",
        back_populates="round",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class StandupEntry(Base, BaseMixin):
    """
    One member's standup answers within a round.

    Attributes:
        round_id: Owning standup round.
        member_id: The team member who responds.
        yesterday / today / blockers: Parsed answers to the 3 questions.
        raw_text: Raw inbound messages (audit trail).
        completed: True once all 3 answers are collected.
        submitted_at: When the entry was completed.
    """

    __tablename__ = "standup_entries"
    __table_args__ = (
        UniqueConstraint("round_id", "member_id", name="uq_standup_entry_round_member"),
    )

    round_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("standup_rounds.id"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("team_members.id"), nullable=False
    )
    yesterday: Mapped[str | None] = mapped_column(Text, nullable=True)
    today: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    round: Mapped["StandupRound"] = relationship(
        "StandupRound", back_populates="entries", lazy="raise"
    )
