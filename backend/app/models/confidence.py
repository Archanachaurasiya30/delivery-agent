"""ConfidenceSnapshot model: the stored daily release-confidence trend."""

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.sprint import Sprint


class ConfidenceSnapshot(Base, BaseMixin):
    """
    One row per (sprint, day): the persisted release-confidence trend.

    The trend line IS the product, not just the latest number, so we store a
    daily confidence value per sprint queryable as a time series. A daily
    Celery job upserts one row per active sprint; the unique constraint on
    ``(sprint_id, snapshot_date)`` makes re-running that job idempotent.

    Attributes:
        sprint_id: The sprint ("release") this confidence is computed for.
        snapshot_date: The calendar day this value represents.
        confidence_value: Composite 0-100 confidence (higher = healthier).
        scope_remaining / velocity_vs_plan / open_blockers / untested_surface:
            The four 0-100 factor sub-scores that compose ``confidence_value``.
        factors: Raw inputs behind the factor scores, for debugging.
    """

    __tablename__ = "confidence_snapshots"

    sprint_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sprints.id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    confidence_value: Mapped[float] = mapped_column(Float, nullable=False)

    # The four factors that compose confidence_value (each normalized 0-100).
    scope_remaining: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity_vs_plan: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_blockers: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    untested_surface: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Raw inputs behind the factor scores, for inspection/debugging.
    factors: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "sprint_id", "snapshot_date", name="uq_confidence_sprint_date"
        ),
    )

    # Relationships - lazy="raise" to catch implicit I/O during async operations
    sprint: Mapped["Sprint"] = relationship(
        "Sprint",
        back_populates="confidence_snapshots",
        lazy="raise",
    )
