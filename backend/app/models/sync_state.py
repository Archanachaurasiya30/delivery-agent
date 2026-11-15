"""SyncState model: tracks the last sync run per external provider."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseMixin


class SyncState(Base, BaseMixin):
    """
    One row per external provider recording the last pull result.

    Attributes:
        provider: Provider key ("mock" | "tfs").
        last_sync_at: When the last pull ran.
        last_status: "ok" | "error".
        last_error: Error message from the last failed run.
        inserted_count / updated_count: Rows touched on the last run.
    """

    __tablename__ = "sync_state"

    provider: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
