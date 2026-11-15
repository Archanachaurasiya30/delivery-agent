"""Widen tasks.title to 255 to match the Azure DevOps System.Title limit.

Real work items from the on-prem instance exceed the original 200 chars, which
aborted the whole sync transaction with StringDataRightTruncationError. Azure
DevOps caps System.Title at 255, so that is the natural width.

Revision ID: 014
Revises: 013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tasks",
        "title",
        existing_type=sa.String(200),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Titles longer than 200 would be truncated on the way back down.
    op.execute("UPDATE tasks SET title = left(title, 200) WHERE length(title) > 200")
    op.alter_column(
        "tasks",
        "title",
        existing_type=sa.String(255),
        type_=sa.String(200),
        existing_nullable=False,
    )
