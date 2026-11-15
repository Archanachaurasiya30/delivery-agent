"""Add task sync columns and sync_state table.

Revision ID: 005
Revises: 004
Create Date: 2026-06-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Task provenance + sync bookkeeping
    op.add_column(
        "tasks",
        sa.Column("source", sa.String(20), nullable=False, server_default="local"),
    )
    op.add_column(
        "tasks",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_external_id", "tasks", ["external_id"])

    # Per-provider sync state
    op.create_table(
        "sync_state",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(10), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("inserted_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", name="uq_sync_state_provider"),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_index("ix_tasks_external_id")
    op.drop_column("tasks", "last_synced_at")
    op.drop_column("tasks", "source")
