"""Add task_status_events — the transition log behind flow metrics.

Revision ID: 013
Revises: 012
Create Date: 2026-08-04

Includes a one-row-per-task synthetic backfill so the flow charts are not
completely empty on day one. Those rows are marked source='backfill' and are
excluded wherever the API reports how far real history goes — they are derived
from each task's current updated_at, not from an observed transition.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_status_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("task_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="api"),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_status_events_task_changed",
        "task_status_events",
        ["task_id", "changed_at"],
    )
    op.create_index(
        "ix_task_status_events_to_changed",
        "task_status_events",
        ["to_status", "changed_at"],
    )

    # Synthetic seed: one row per existing task at its current status. Flagged
    # so nothing downstream mistakes it for a measured transition.
    op.execute(
        """
        INSERT INTO task_status_events
            (id, task_id, from_status, to_status, changed_at, source, created_at)
        SELECT
            gen_random_uuid(),
            t.id,
            NULL,
            t.status,
            COALESCE(t.updated_at, t.created_at, now()),
            'backfill',
            now()
        FROM tasks t
        """
    )


def downgrade() -> None:
    op.drop_index("ix_task_status_events_to_changed", table_name="task_status_events")
    op.drop_index("ix_task_status_events_task_changed", table_name="task_status_events")
    op.drop_table("task_status_events")
