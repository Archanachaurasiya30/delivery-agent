"""AgentRun model: the coding-agent PR-loop state machine for one task."""

from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseMixin


class AgentRun(Base, BaseMixin):
    """One coding-agent run for a task (1—1 Task, 1—1 Proposal once a PR opens).

    Status lifecycle:
        dispatched → groomed → (skipped_human_only | running)
        running → ci_pending → {pr_open (CI green) | ci_failed (CI red) | re-poll}
        pr_open → merged (Task→done)   |   failed (caps hit / unrecoverable)

    The PR only becomes a reviewable Proposal (``proposal_id`` set, state
    pending_review) once CI is green — the CI gate. ``iteration`` and
    ``cost_estimate`` bound the revise loop; ``ci_poll_count`` keeps the mock
    CI deterministic and bounds "CI never returns".
    """

    __tablename__ = "agent_runs"

    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False, unique=True
    )
    proposal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("proposals.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="dispatched", nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Target repository (name or URL) chosen at dispatch time. Overrides the
    # globally-configured repo for the adapter; null falls back to config.
    repository: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pr_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ci_poll_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Last AgentRunResult (branch/diff/pr/summary) — used to build the Proposal
    # when CI goes green and to carry the diff into the revise loop.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
