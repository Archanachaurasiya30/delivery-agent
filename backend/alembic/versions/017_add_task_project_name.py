"""Store the Azure DevOps sub-area on tasks so the board can group by it.

The provider already derives ``project_name`` from the area path
("Northwind\\Retail Platform\\Storefront" -> "Storefront") but
the import discarded it. Nothing real was left to group cards by, so the UI
fabricated a team badge from a hash of the task id and rendered invented
".NET / Android / iOS" labels on real work items.

Revision ID: 017
Revises: 016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("project_name", sa.String(100), nullable=True),
    )
    op.create_index("ix_tasks_project_name", "tasks", ["project_name"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project_name", table_name="tasks")
    op.drop_column("tasks", "project_name")
