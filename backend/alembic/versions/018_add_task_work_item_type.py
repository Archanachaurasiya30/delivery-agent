"""Store the Azure DevOps work item type on tasks.

The sync already imports Bugs, Issues, Features, PBIs and Tasks — the provider
filters on type — but then threw the type away. 35 Bugs and 102 Issues were
sitting in the board indistinguishable from ordinary tasks, so there was no way
to ask "what is broken in this stream?".

Revision ID: 018
Revises: 017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("work_item_type", sa.String(50), nullable=True),
    )
    op.create_index("ix_tasks_work_item_type", "tasks", ["work_item_type"])


def downgrade() -> None:
    op.drop_index("ix_tasks_work_item_type", table_name="tasks")
    op.drop_column("tasks", "work_item_type")
