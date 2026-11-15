"""Stream model: a portfolio-altitude grouping of sprints owned by a PM."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.feature import Feature
    from app.models.sprint import Sprint


class Stream(Base, BaseMixin):
    """
    A named group of sprints (a delivery stream) with a PM owner.

    Status and direction are deliberately NOT stored here. They are always
    derived at request time from the confidence of the stream's child sprints
    (see ``ConfidenceService.get_stream_rollup``). Storing a manual status
    would violate the Phase 1 invariant that a stream's health rolls up from
    its children.

    Attributes:
        name: Stream name (e.g., "Storefront").
        description: Optional human description of the stream.
        owner_id: Team member (the PM) who owns this stream.
    """

    __tablename__ = "streams"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("team_members.id"),
        nullable=True,
    )

    # Relationships - lazy="raise" to catch implicit I/O during async operations
    sprints: Mapped[list["Sprint"]] = relationship(
        "Sprint",
        back_populates="stream",
        lazy="raise",
    )
    features: Mapped[list["Feature"]] = relationship(
        "Feature",
        back_populates="stream",
        lazy="raise",
    )
