"""AgentRunEvent model: an append-only progress log for one coding-agent run.

Each row is one telemetry event (workspace prepared, turn completed, PR opened,
…) emitted while a run executes. ``seq`` orders events within a run and lets
the UI poll incrementally ("give me everything after seq N"). Events are pure
telemetry — they never drive the run state machine, which lives on AgentRun.
"""

from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseMixin


class AgentRunEvent(Base, BaseMixin):
    """One progress event for an AgentRun (ordered by ``seq`` within the run)."""

    __tablename__ = "agent_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_run_events_run_seq"),
        Index("ix_agent_run_events_run_id_seq", "run_id", "seq"),
    )

    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_runs.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    # Coarse event category, e.g. "workspace", "turn", "pr", "error".
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional structured detail (tool name, file list, cost, …).
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
