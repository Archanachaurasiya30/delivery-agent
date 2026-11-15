"""Append-only log of task status transitions.

Flow metrics — cycle time, lead time, throughput, aging WIP, a cumulative flow
diagram — cannot be derived from the confidence snapshots. A snapshot records a
daily *position*; these questions need the *transitions*. This table is the only
honest source for them.

It also gives blocked-detection a real signal. Today "blocked" is inferred from
``Task.updated_at`` being stale, which the autopilot nudge writes to and which
provider sync rewrites in bulk. "Entered in_progress N days ago and has not
left" is immune to both.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TaskStatusEvent(Base, BaseMixin):
    """One status transition for one task.

    Attributes:
        from_status: Previous status. None for the task's first observation.
        to_status: Status after the transition.
        changed_at: When it happened (not when the row was written).
        source: Who caused it — ``api``, ``sync``, ``agent``, or ``backfill``.
            ``backfill`` rows are synthetic, written once by migration 013 from
            each task's ``updated_at`` so charts are not empty on day one. They
            are excluded from ``history_starts`` because they are not real
            observations.
        changed_by: Free-form actor label. There is no auth yet, so this is
            advisory.
    """

    __tablename__ = "task_status_events"

    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), default="api", nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    task: Mapped["Task"] = relationship("Task", lazy="raise")

    __table_args__ = (
        # Per-task replay (cycle time) and per-status windows (throughput, CFD).
        Index("ix_task_status_events_task_changed", "task_id", "changed_at"),
        Index("ix_task_status_events_to_changed", "to_status", "changed_at"),
    )
