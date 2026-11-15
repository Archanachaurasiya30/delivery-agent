"""Keep the raw Azure DevOps signals blocker detection needs.

The sync collapsed ADO's state into five statuses, so "On Hold" became plain
"in_progress", and it never stored when the state changed, so staleness was
measured against our own sync time (meaningless). These columns keep what ADO
actually says: the raw state, when it last changed, the tags, and the
"Why On Hold" reason the team fills in.

Revision ID: 019
Revises: 018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("external_state", sa.String(50), nullable=True))
    op.add_column(
        "tasks", sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "tasks", sa.Column("external_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("tasks", sa.Column("tags", sa.String(500), nullable=True))
    op.add_column("tasks", sa.Column("hold_reason", sa.Text, nullable=True))


def downgrade() -> None:
    for col in ("hold_reason", "tags", "external_changed_at", "state_changed_at", "external_state"):
        op.drop_column("tasks", col)
