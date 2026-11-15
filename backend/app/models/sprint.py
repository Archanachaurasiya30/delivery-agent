"""Sprint model for iteration planning."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.confidence import ConfidenceSnapshot
    from app.models.stream import Stream
    from app.models.task import Task


class Sprint(Base, BaseMixin):
    """
    Sprint model representing a time-boxed iteration.

    Attributes:
        name: Sprint name (e.g., "Sprint 23")
        goal: Sprint goal description
        start_date: Sprint start date
        end_date: Sprint end date
        status: Sprint status (planning, active, completed, cancelled)
        capacity_hours: Total team capacity in hours for this sprint
        velocity: Actual story points completed (set after sprint ends)
        retrospective_notes: Notes from sprint retrospective
    """

    __tablename__ = "sprints"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planning", nullable=False)
    capacity_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    velocity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrospective_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Team capacity breakdown per member (JSON: {member_id: hours})
    capacity_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Optional parent stream (portfolio-altitude grouping). Nullable so existing
    # standalone sprints keep working.
    stream_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("streams.id"),
        nullable=True,
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="sprint",
        lazy="raise",
    )
    stream: Mapped["Stream | None"] = relationship(
        "Stream",
        back_populates="sprints",
        lazy="raise",
    )
    confidence_snapshots: Mapped[list["ConfidenceSnapshot"]] = relationship(
        "ConfidenceSnapshot",
        back_populates="sprint",
        lazy="raise",
    )
