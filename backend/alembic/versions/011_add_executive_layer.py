"""Add executive layer: briefs, app_settings, task autopilot columns.

Revision ID: 011
Revises: 010
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One persisted morning brief per calendar day (unique date => idempotent
    # regeneration upserts the same row).
    op.create_table(
        "briefs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("brief_date", sa.Date(), nullable=False, unique=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # DB-backed key/value store for runtime settings (the autopilot dial lives
    # here so it can be flipped live without a redeploy).
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Autopilot bookkeeping on tasks (additive, nullable):
    # autopilot_state: null | suggested | dispatched | skipped
    # autopilot_nudged_at: last stale-task Telegram nudge (24h dedupe guard)
    op.add_column("tasks", sa.Column("autopilot_state", sa.String(20), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("autopilot_nudged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "autopilot_nudged_at")
    op.drop_column("tasks", "autopilot_state")
    op.drop_table("app_settings")
    op.drop_table("briefs")
