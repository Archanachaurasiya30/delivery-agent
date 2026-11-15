"""Add streams, confidence snapshots, and proposal scope/escalation.

Revision ID: 006
Revises: 005
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Portfolio-altitude grouping of sprints. Created first so the FKs below
    # (sprints.stream_id, proposals.stream_id) can reference it.
    op.create_table(
        "streams",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("team_members.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Each sprint may belong to a stream (nullable: standalone sprints stay valid).
    op.add_column(
        "sprints",
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("streams.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_sprints_stream_id", "sprints", ["stream_id"])

    # Proposal altitude + escalation routing.
    op.add_column(
        "proposals",
        sa.Column("scope", sa.String(20), nullable=False, server_default="project"),
    )
    op.add_column(
        "proposals",
        sa.Column(
            "escalated", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "proposals",
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("streams.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_proposals_scope", "proposals", ["scope"])

    # Daily release-confidence trend, one row per (sprint, day).
    op.create_table(
        "confidence_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "sprint_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sprints.id"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("confidence_value", sa.Float(), nullable=False),
        sa.Column("scope_remaining", sa.Float(), nullable=False, server_default="0"),
        sa.Column("velocity_vs_plan", sa.Float(), nullable=False, server_default="0"),
        sa.Column("open_blockers", sa.Float(), nullable=False, server_default="0"),
        sa.Column("untested_surface", sa.Float(), nullable=False, server_default="0"),
        sa.Column("factors", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "sprint_id", "snapshot_date", name="uq_confidence_sprint_date"
        ),
    )
    op.create_index(
        "ix_confidence_sprint_date",
        "confidence_snapshots",
        ["sprint_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_confidence_sprint_date")
    op.drop_table("confidence_snapshots")

    op.drop_index("ix_proposals_scope")
    op.drop_column("proposals", "stream_id")
    op.drop_column("proposals", "escalated")
    op.drop_column("proposals", "scope")

    op.drop_index("ix_sprints_stream_id")
    op.drop_column("sprints", "stream_id")

    op.drop_table("streams")
