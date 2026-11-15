"""Initial schema with team_members, tasks, and proposals tables.

Revision ID: 001
Revises:
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create team_members table
    op.create_table(
        "team_members",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="developer"),
        sa.Column("capacity_hours_per_sprint", sa.Integer, nullable=False, server_default="40"),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="backlog"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column(
            "assignee_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("team_members.id"),
            nullable=True,
        ),
        sa.Column("story_points", sa.Integer, nullable=True),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create proposals table
    op.create_table(
        "proposals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("content", postgresql.JSONB, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("created_by_agent", sa.String(100), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prompt_log", postgresql.JSONB, nullable=True),
        sa.Column("execution_result", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for common queries
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_index("ix_proposals_state", "proposals", ["state"])
    op.create_index("ix_proposals_type", "proposals", ["type"])


def downgrade() -> None:
    op.drop_index("ix_proposals_type")
    op.drop_index("ix_proposals_state")
    op.drop_index("ix_tasks_assignee_id")
    op.drop_index("ix_tasks_status")
    op.drop_table("proposals")
    op.drop_table("tasks")
    op.drop_table("team_members")
