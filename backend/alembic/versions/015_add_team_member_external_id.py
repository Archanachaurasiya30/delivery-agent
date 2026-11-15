"""Add team_members.external_id so synced people key on their ADO identity.

Assignees were matched by display name, which silently failed against the real
instance: the seeded rows are near-misses of real people ("Diego Alvarez" vs
"Diego Álvarez"), so 0 of 77 Sprint 2404 tasks resolved an assignee. Work
items carry a stable identity GUID in System.AssignedTo.id — that is the key.

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_members",
        sa.Column("external_id", sa.String(64), nullable=True),
    )
    # Nullable + unique: locally created members have no external identity, and
    # Postgres allows many NULLs under a unique constraint.
    op.create_index(
        "ix_team_members_external_id",
        "team_members",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_team_members_external_id", table_name="team_members")
    op.drop_column("team_members", "external_id")
