"""Feature model: a deliverable grouping of tasks within a stream.

A Feature is the "what" a user story belongs to (e.g. "Group Messaging"),
sitting alongside the Sprint, which is the "when". Both are children of a
Stream and both are optional on a Task:

    Stream ─┬─< Sprint  ─< Task   (when)
            └─< Feature ─< Task   (what)
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.stream import Stream
    from app.models.task import Task


class Feature(Base, BaseMixin):
    """
    A named feature (deliverable) belonging to a stream, grouping tasks.

    Attributes:
        name: Feature name (e.g., "Group Messaging").
        description: Optional human description.
        stream_id: Owning stream (nullable so a feature can be created before
            it is tied to a stream).
    """

    __tablename__ = "features"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stream_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("streams.id"),
        nullable=True,
    )

    # Relationships - lazy="raise" to catch implicit I/O during async operations
    stream: Mapped["Stream | None"] = relationship(
        "Stream",
        back_populates="features",
        lazy="raise",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="feature",
        lazy="raise",
    )
