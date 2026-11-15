"""Add acceptance_criteria to tasks.

Revision ID: 012
Revises: 011
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("acceptance_criteria", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "acceptance_criteria")
