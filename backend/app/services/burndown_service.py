"""Historical burndown, replayed from the daily confidence snapshots.

The history was always there. ``ConfidenceService.compute_sprint_factors``
writes ``actual_remaining`` and ``ideal_remaining`` into
``ConfidenceSnapshot.factors`` once per sprint per day, via the beat job at
``CONFIDENCE_SNAPSHOT_CRON`` (23:30 by default) — an end-of-day reading, which
is exactly the right sample point for a burndown. Nobody ever read it back.

The previous implementation instead re-queried *current* done-points inside the
day loop, so every past date got today's value and the actual line was flat.
That bug also fed ``velocity_vs_plan``.

Two rules hold here:

1. **Never invent a reading.** A day with no snapshot is ``None``, not zero and
   not carried forward from the previous day. The chart breaks the line.
2. **The ideal line is computed, never replayed.** It is a deterministic
   function of the sprint window, so it stays straight across missing days.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.confidence import ConfidenceSnapshot
from app.schemas.sprint import BurndownDataPoint, SprintBurndown
from app.services.sprint_service import SprintService


class BurndownService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sprints = SprintService(db)

    async def get_series(self, sprint_id: UUID) -> SprintBurndown:
        sprint = await self.sprints.get_sprint(sprint_id)

        # Today's live reading also gives us the authoritative total, which can
        # differ from any historical snapshot if scope changed.
        _, actual_today = await self.sprints.get_today_burndown_point(sprint_id)
        total_points, _, unit = await self.sprints.work_units(sprint_id)

        snapshots = await self._snapshot_readings(str(sprint_id))

        today = date.today()
        points: list[BurndownDataPoint] = []
        cursor = sprint.start_date
        while cursor <= sprint.end_date:
            ideal = SprintService.ideal_remaining_on(
                cursor, sprint.start_date, sprint.end_date, float(total_points)
            )

            if cursor == today:
                remaining: float | None = actual_today
                source: str | None = "live"
            elif cursor < today and cursor in snapshots:
                remaining = snapshots[cursor]
                source = "snapshot"
            else:
                # Future date, or a past day the snapshot job never covered.
                remaining = None
                source = None

            points.append(
                BurndownDataPoint(
                    date=cursor,
                    remaining_points=None if remaining is None else round(remaining),
                    ideal_points=ideal,
                    source=source,
                )
            )
            cursor += timedelta(days=1)

        return SprintBurndown(
            sprint_id=sprint.id,
            sprint_name=sprint.name,
            total_points=total_points,
            unit=unit,
            data_points=points,
        )

    async def _snapshot_readings(self, sprint_id: str) -> dict[date, float]:
        """``{snapshot_date: actual_remaining}`` from the stored raw factors.

        Rows written before ``actual_remaining`` was recorded are skipped rather
        than defaulted — a missing key means we did not measure that day.
        """
        result = await self.db.execute(
            select(ConfidenceSnapshot.snapshot_date, ConfidenceSnapshot.factors)
            .where(ConfidenceSnapshot.sprint_id == sprint_id)
            .order_by(ConfidenceSnapshot.snapshot_date)
        )
        readings: dict[date, float] = {}
        for snapshot_date, factors in result.all():
            if not factors:
                continue
            value = factors.get("actual_remaining")
            if value is None:
                continue
            try:
                readings[snapshot_date] = float(value)
            except (TypeError, ValueError):
                continue
        return readings
