"""Brief model: one persisted executive morning brief per calendar day."""

from datetime import date
from typing import Any

from sqlalchemy import Date, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseMixin


class Brief(Base, BaseMixin):
    """One morning brief per day.

    ``brief_date`` is unique so regenerating a brief for the same day upserts
    the existing row instead of creating a duplicate (idempotent per date).
    """

    __tablename__ = "briefs"

    brief_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured brief body, e.g. {shipped[], ai_delivered[], risks[],
    # needs_decision[], numbers{}, narrative}.
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
