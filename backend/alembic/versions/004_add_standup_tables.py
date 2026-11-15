"""Add standup_rounds and standup_entries tables.

Revision ID: 004
Revises: 003
Create Date: 2026-06-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "standup_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="collecting"),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("scheduled_for", sa.Date, nullable=True),
        sa.Column("expected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proposals.id"),
            nullable=True,
        ),
        sa.Column("summary", postgresql.JSONB, nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "standup_entries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "round_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("standup_rounds.id"),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("team_members.id"),
            nullable=False,
        ),
        sa.Column("yesterday", sa.Text, nullable=True),
        sa.Column("today", sa.Text, nullable=True),
        sa.Column("blockers", sa.Text, nullable=True),
        sa.Column("raw_text", postgresql.JSONB, nullable=True),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "round_id", "member_id", name="uq_standup_entry_round_member"
        ),
    )

    op.create_index("ix_standup_rounds_status", "standup_rounds", ["status"])
    op.create_index("ix_standup_entries_round_id", "standup_entries", ["round_id"])


def downgrade() -> None:
    op.drop_index("ix_standup_entries_round_id")
    op.drop_index("ix_standup_rounds_status")
    op.drop_table("standup_entries")
    op.drop_table("standup_rounds")
