"""Add Telegram link fields to team_members.

Revision ID: 003
Revises: 002
Create Date: 2026-06-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_members",
        sa.Column("telegram_chat_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "team_members",
        sa.Column("telegram_username", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_team_members_telegram_chat_id", "team_members", ["telegram_chat_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_team_members_telegram_chat_id", "team_members", type_="unique"
    )
    op.drop_column("team_members", "telegram_username")
    op.drop_column("team_members", "telegram_chat_id")
