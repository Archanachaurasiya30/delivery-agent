"""AppSetting model: DB-backed key/value store for runtime settings."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSetting(Base):
    """One runtime setting (e.g. the autopilot dial) as a key → JSON value.

    Deliberately NOT BaseMixin: the natural string key IS the primary key and
    rows are upserted in place, so a surrogate UUID id / created_at would just
    be noise. Storing state here (instead of env/config) is what makes settings
    live-togglable without a redeploy.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
