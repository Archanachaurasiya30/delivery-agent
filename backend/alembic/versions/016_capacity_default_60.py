"""Move the per-sprint capacity default from 40 to 60 hours.

40h was the seeded demo figure. Northwind sprints are two weeks (10 working
days), so 40 read as badly under-capacity against genuine assigned hours —
Sprint 2404 alone carries 455h. The on-prem instance leaves the sprint
Capacity tab empty, so this default is what every synced member gets until
per-person hours exist.

Only rows still sitting on the old default are moved; anything set by hand is
left alone.

Revision ID: 016
Revises: 015
"""

from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE team_members SET capacity_hours_per_sprint = 60 "
        "WHERE capacity_hours_per_sprint = 40"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE team_members SET capacity_hours_per_sprint = 40 "
        "WHERE capacity_hours_per_sprint = 60"
    )
