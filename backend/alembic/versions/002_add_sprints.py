"""Add sprints table and update tasks with sprint_id and priority_order.

Revision ID: 002
Revises: 001
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sprints table
    op.create_table(
        "sprints",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planning"),
        sa.Column("capacity_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("velocity", sa.Integer, nullable=True),
        sa.Column("retrospective_notes", sa.Text, nullable=True),
        sa.Column("capacity_breakdown", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add sprint_id and priority_order to tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "sprint_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sprints.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("priority_order", sa.Integer, nullable=False, server_default="0"),
    )

    # Create indexes
    op.create_index("ix_sprints_status", "sprints", ["status"])
    op.create_index("ix_sprints_start_date", "sprints", ["start_date"])
    op.create_index("ix_tasks_sprint_id", "tasks", ["sprint_id"])
    op.create_index("ix_tasks_priority_order", "tasks", ["priority_order"])


def downgrade() -> None:
    op.drop_index("ix_tasks_priority_order")
    op.drop_index("ix_tasks_sprint_id")
    op.drop_index("ix_sprints_start_date")
    op.drop_index("ix_sprints_status")
    op.drop_column("tasks", "priority_order")
    op.drop_column("tasks", "sprint_id")
    op.drop_table("sprints")
