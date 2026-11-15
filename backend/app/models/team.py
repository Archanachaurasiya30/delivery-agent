"""TeamMember model for team management."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TeamMember(Base, BaseMixin):
    """
    Team member model representing a person on the delivery team.

    Attributes:
        name: Full name of the team member
        email: Unique email address
        role: Team role (e.g., developer, lead, qa)
        capacity_hours_per_sprint: Available hours per sprint
        is_available: Whether the team member is currently available
        external_id: Identity id in the external system (ADO System.AssignedTo.id)
    """

    __tablename__ = "team_members"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="developer", nullable=False)
    # 60h per two-week sprint. The on-prem instance leaves the sprint Capacity
    # tab empty, so this default is what every synced member gets.
    capacity_hours_per_sprint: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Stable identity in the external system. Display names do not survive a
    # real instance (spelling variants, renames), so assignee matching keys on
    # this instead; NULL for people created locally.
    external_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    # Telegram link (set via the /start <code> registration flow). The numeric
    # Telegram chat id (stored as string) is the durable DM target.
    telegram_chat_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True
    )
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships - use lazy="raise" to catch implicit I/O during async operations
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="assignee",
        lazy="raise",
    )
