"""Add features table, tasks.feature_id, and agent_runs.repository.

Introduces a first-class Feature entity (Stream -> Feature -> Task) and a
per-dispatch target repository for the coding agent.

Revision ID: 009
Revises: 008
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("streams.id"),
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
    op.create_index("ix_features_stream_id", "features", ["stream_id"])

    op.add_column(
        "tasks",
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("features.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("repository", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "repository")
    op.drop_column("tasks", "feature_id")
    op.drop_index("ix_features_stream_id")
    op.drop_table("features")
