"""Task model for work item management."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.feature import Feature
    from app.models.sprint import Sprint
    from app.models.team import TeamMember


class Task(Base, BaseMixin):
    """
    Task model representing a work item in the backlog.

    Attributes:
        title: Task title
        description: Detailed description
        status: Current status (backlog, todo, in_progress, review, done)
        priority: Task priority (low, medium, high, critical)
        assignee_id: Optional assigned team member
        sprint_id: Optional sprint this task belongs to
        story_points: Estimated effort in story points
        priority_order: Order within backlog/sprint (lower = higher priority)
        external_id: Reference to external system (mock integration)
    """

    __tablename__ = "tasks"

    # 255 matches the Azure DevOps System.Title limit — see migration 014.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Definition of done for the story. Maps to ADO's
    # Microsoft.VSTS.Common.AcceptanceCriteria when the provider supports it.
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="backlog", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("team_members.id"),
        nullable=True,
    )
    sprint_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sprints.id"),
        nullable=True,
    )
    # Optional parent feature (the "what" this task delivers), independent of
    # the sprint (the "when"). Both roll up to a stream.
    feature_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("features.id"),
        nullable=True,
    )
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Estimated effort in hours (distinct from story_points). Used by the
    # authoring form and capacity views.
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Technology / platform track (e.g. ".NET", "iOS"). Free string so it can
    # carry whatever the team uses; the form offers the known set.
    technology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Sub-area within the stream, from the Azure DevOps area path
    # ("...\Retail Platform\Storefront" -> "Storefront"). NULL
    # for items filed directly on the stream root. This is the only real
    # grouping synced work carries, so the board groups cards by it.
    project_name: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )
    # Azure DevOps work item type ("Bug", "Issue", "Task", "Feature", ...).
    # NULL on locally created tasks.
    work_item_type: Mapped[str | None] = mapped_column(
        String(50), index=True, nullable=True
    )
    # Raw Azure DevOps signals (migration 019). ``status`` is a lossy mapping
    # ("On Hold" -> in_progress), so blocker detection reads these instead.
    external_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    external_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Where this task originated. "local" tasks are pushed to the external
    # provider; "tfs" tasks came FROM the provider and must NOT be pushed back
    # (prevents the push<->pull echo loop).
    source: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Delivery-autopilot bookkeeping. ``autopilot_state`` records what the
    # autopilot decided for this task (null | suggested | dispatched | skipped);
    # ``autopilot_nudged_at`` dedupes stale-task Telegram nudges (24h guard).
    autopilot_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    autopilot_nudged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships - use lazy="raise" to catch implicit I/O during async operations
    assignee: Mapped["TeamMember | None"] = relationship(
        "TeamMember",
        back_populates="tasks",
        lazy="raise",
    )
    sprint: Mapped["Sprint | None"] = relationship(
        "Sprint",
        back_populates="tasks",
        lazy="raise",
    )
    feature: Mapped["Feature | None"] = relationship(
        "Feature",
        back_populates="tasks",
        lazy="raise",
    )
