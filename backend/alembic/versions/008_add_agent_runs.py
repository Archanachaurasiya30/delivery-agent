"""Add agent_runs (coding-agent PR-loop state machine).

Revision ID: 008
Revises: 007
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proposals.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="dispatched"),
        sa.Column("branch_name", sa.String(200), nullable=True),
        sa.Column("pr_id", sa.String(100), nullable=True),
        sa.Column("pr_url", sa.String(500), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_estimate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ci_poll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spec", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("last_review_comment", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_id", name="uq_agent_runs_task_id"),
    )
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_status")
    op.drop_table("agent_runs")
