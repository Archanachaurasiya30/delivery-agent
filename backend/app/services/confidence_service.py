"""Confidence/forecast service: per-sprint release confidence + stream rollup.

Confidence is a 0-100 value (higher = healthier) composed from four factors and
persisted daily as a :class:`ConfidenceSnapshot`, so the trend is queryable as a
time series rather than a single point. A stream's qualitative status and
direction are DERIVED here from its child sprints' confidence — never stored on
the ``Stream`` row — which keeps "stream health rolls up from children" true by
construction.
"""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import DatabaseTools
from app.models.confidence import ConfidenceSnapshot
from app.models.sprint import Sprint
from app.models.task import Task
from app.services.sprint_service import SprintService

logger = logging.getLogger(__name__)

# Factor weights (sum to 1.0). Schedule (scope + velocity = 65%) dominates;
# blockers and untested surface refine.
_W_SCOPE = 0.35
_W_VELOCITY = 0.30
_W_BLOCKERS = 0.20
_W_UNTESTED = 0.15

# Worst-child ordering for stream status rollup (lower = worse).
_BAND_ORDER = {"Behind": 0, "At risk": 1, "On track": 2, "Ahead": 3}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


class ConfidenceService:
    """Computes, persists, and rolls up release confidence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tools = DatabaseTools(db)
        self._sprints = SprintService(db)

    # --- factor + value computation -------------------------------------

    async def _points_by_status(self, sprint_id: str) -> dict[str, int]:
        result = await self.db.execute(
            select(Task.status, func.coalesce(func.sum(Task.story_points), 0))
            .where(Task.sprint_id == sprint_id)
            .group_by(Task.status)
        )
        return {row[0]: int(row[1] or 0) for row in result.all()}

    async def compute_sprint_factors(self, sprint_id: str) -> dict[str, Any] | None:
        """Compute the four 0-100 factor sub-scores for a sprint.

        Returns ``None`` when the sprint has no tasks (nothing to assess) so the
        caller can skip it in a stream rollup instead of dragging health down.
        Reuses the existing release-readiness heuristic (completion + blockers)
        and ``SprintService.get_burndown`` (velocity-vs-plan). ``untested_surface``
        is a proxy: story points stuck in ``review`` relative to coded work,
        since the system has no real test-coverage signal.
        """
        readiness = await self._tools.get_release_readiness(sprint_id)
        if "error" in readiness:
            return None

        total = readiness["tasks_done"] + readiness["tasks_remaining"]
        if total <= 0:
            return None

        completion_rate = float(readiness["completion_rate"])  # 0-100, by task count
        blocked = int(readiness["tasks_blocked"])

        # LIVE state only. Never SprintService.get_burndown() — that replays
        # these very snapshots, so reading it here would make confidence a
        # function of yesterday's confidence and drift silently.
        ideal_remaining, actual_remaining = await self._sprints.get_today_burndown_point(
            sprint_id
        )
        ratio = actual_remaining / max(ideal_remaining, 1.0)

        points = await self._points_by_status(sprint_id)
        review_points = points.get("review", 0)
        done_points = points.get("done", 0)
        total_points = sum(points.values())
        untested = review_points / max(done_points + review_points, 1)

        scope_remaining = _clamp(completion_rate)
        velocity_vs_plan = _clamp(100.0 - max(0.0, ratio - 1.0) * 100.0)
        open_blockers = _clamp(100.0 - blocked * 25.0)
        untested_surface = _clamp(100.0 - untested * 100.0)

        return {
            "scope_remaining": round(scope_remaining, 1),
            "velocity_vs_plan": round(velocity_vs_plan, 1),
            "open_blockers": round(open_blockers, 1),
            "untested_surface": round(untested_surface, 1),
            "raw": {
                "completion_rate": completion_rate,
                "blocked": blocked,
                "ideal_remaining": ideal_remaining,
                # Read back by BurndownService to rebuild the historical actual
                # line — this dict IS the burndown history.
                "actual_remaining": actual_remaining,
                # Lets the burndown show scope change from the next snapshot on.
                # Rows written before this existed simply lack the key.
                "total_points": total_points,
                "review_points": review_points,
                "done_points": done_points,
                "schedule_ahead": actual_remaining < ideal_remaining * 0.85,
            },
        }

    def compute_confidence_value(self, factors: dict[str, Any]) -> float:
        """Weighted blend of the four factor sub-scores → 0-100."""
        value = (
            _W_SCOPE * factors["scope_remaining"]
            + _W_VELOCITY * factors["velocity_vs_plan"]
            + _W_BLOCKERS * factors["open_blockers"]
            + _W_UNTESTED * factors["untested_surface"]
        )
        return round(value, 1)

    # --- persistence ----------------------------------------------------

    async def snapshot_sprint(
        self, sprint_id: str, on_date: date | None = None
    ) -> ConfidenceSnapshot | None:
        """Upsert one snapshot for (sprint, day). Idempotent within a day.

        Returns ``None`` for sprints with no tasks (skipped).
        """
        on_date = on_date or date.today()
        factors = await self.compute_sprint_factors(sprint_id)
        if factors is None:
            return None
        value = self.compute_confidence_value(factors)

        result = await self.db.execute(
            select(ConfidenceSnapshot).where(
                ConfidenceSnapshot.sprint_id == sprint_id,
                ConfidenceSnapshot.snapshot_date == on_date,
            )
        )
        snap = result.scalar_one_or_none()
        if snap is None:
            snap = ConfidenceSnapshot(sprint_id=sprint_id, snapshot_date=on_date)
            self.db.add(snap)

        snap.confidence_value = value
        snap.scope_remaining = factors["scope_remaining"]
        snap.velocity_vs_plan = factors["velocity_vs_plan"]
        snap.open_blockers = factors["open_blockers"]
        snap.untested_surface = factors["untested_surface"]
        snap.factors = factors["raw"]
        await self.db.flush()
        return snap

    # --- reads ----------------------------------------------------------

    async def get_sprint_trend(
        self, sprint_id: str, days: int = 14
    ) -> list[ConfidenceSnapshot]:
        since = date.today() - timedelta(days=days)
        result = await self.db.execute(
            select(ConfidenceSnapshot)
            .where(
                ConfidenceSnapshot.sprint_id == sprint_id,
                ConfidenceSnapshot.snapshot_date >= since,
            )
            .order_by(ConfidenceSnapshot.snapshot_date)
        )
        return list(result.scalars().all())

    async def get_latest_snapshot(
        self, sprint_id: str
    ) -> ConfidenceSnapshot | None:
        result = await self.db.execute(
            select(ConfidenceSnapshot)
            .where(ConfidenceSnapshot.sprint_id == sprint_id)
            .order_by(ConfidenceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_value(self, sprint_id: str) -> float | None:
        snap = await self.get_latest_snapshot(sprint_id)
        return snap.confidence_value if snap else None

    async def latest_snapshots_for(
        self, sprint_ids: list[str]
    ) -> dict[str, ConfidenceSnapshot]:
        """Latest snapshot per sprint, in ONE query.

        Replaces a per-sprint ``get_latest_snapshot`` loop. ``/portfolio`` calls
        ``get_stream_rollup`` once per stream, which called that loop once per
        sprint — O(streams x sprints) round trips on the executive landing page,
        which the dashboards now poll harder.
        """
        if not sprint_ids:
            return {}
        result = await self.db.execute(
            select(ConfidenceSnapshot)
            .where(ConfidenceSnapshot.sprint_id.in_(sprint_ids))
            # Postgres DISTINCT ON: first row per sprint under this ORDER BY.
            .distinct(ConfidenceSnapshot.sprint_id)
            .order_by(
                ConfidenceSnapshot.sprint_id,
                ConfidenceSnapshot.snapshot_date.desc(),
            )
        )
        return {snap.sprint_id: snap for snap in result.scalars().all()}

    @staticmethod
    def value_to_band(value: float | None, schedule_ahead: bool = False) -> str:
        """Map a 0-100 confidence value to a qualitative band."""
        if value is None:
            return "No data"
        if value >= 75:
            return "Ahead" if schedule_ahead else "On track"
        if value >= 60:
            return "At risk"
        return "Behind"

    async def get_sprint_confidence(self, sprint: Sprint) -> dict[str, Any]:
        """Assemble the precise per-sprint confidence card (value + factors + trend)."""
        snap = await self.get_latest_snapshot(sprint.id)
        trend = await self.get_sprint_trend(sprint.id, days=14)
        trend_points = [
            {"date": s.snapshot_date, "value": s.confidence_value} for s in trend
        ]
        if snap is None:
            return {
                "sprint_id": sprint.id,
                "sprint_name": sprint.name,
                "status": "No data",
                "confidence_value": None,
                "factors": None,
                "trend": trend_points,
            }
        schedule_ahead = bool((snap.factors or {}).get("schedule_ahead", False))
        return {
            "sprint_id": sprint.id,
            "sprint_name": sprint.name,
            "status": self.value_to_band(snap.confidence_value, schedule_ahead),
            "confidence_value": snap.confidence_value,
            "factors": {
                "scope_remaining": snap.scope_remaining,
                "velocity_vs_plan": snap.velocity_vs_plan,
                "open_blockers": snap.open_blockers,
                "untested_surface": snap.untested_surface,
            },
            "trend": trend_points,
        }

    # --- stream rollup (derived, never stored) --------------------------

    async def _stream_sprints(
        self, stream_id: str, statuses: tuple[str, ...] = ("active", "planning")
    ) -> list[Sprint]:
        result = await self.db.execute(
            select(Sprint)
            .where(Sprint.stream_id == stream_id, Sprint.status.in_(statuses))
            .order_by(Sprint.start_date)
        )
        return list(result.scalars().all())

    @classmethod
    def _worst_band(cls, bands: list[str]) -> str:
        real = [b for b in bands if b in _BAND_ORDER]
        if not real:
            return "No data"
        return min(real, key=lambda b: _BAND_ORDER[b])

    async def _stream_direction(
        self, sprint_ids: list[str], days: int = 14
    ) -> str:
        """Slope of the stored daily mean confidence over the window."""
        if not sprint_ids:
            return "steady"
        since = date.today() - timedelta(days=days)
        result = await self.db.execute(
            select(
                ConfidenceSnapshot.snapshot_date,
                func.avg(ConfidenceSnapshot.confidence_value),
            )
            .where(
                ConfidenceSnapshot.sprint_id.in_(sprint_ids),
                ConfidenceSnapshot.snapshot_date >= since,
            )
            .group_by(ConfidenceSnapshot.snapshot_date)
            .order_by(ConfidenceSnapshot.snapshot_date)
        )
        series = [float(row[1]) for row in result.all()]
        if len(series) < 2:
            return "steady"
        head = series[: min(3, len(series))]
        tail = series[-min(3, len(series)) :]
        slope = (sum(tail) / len(tail)) - (sum(head) / len(head))
        if slope > 3:
            return "improving"
        if slope < -3:
            return "declining"
        return "steady"

    async def get_stream_rollup(self, stream_id: str) -> dict[str, Any]:
        """Derive a stream's qualitative status + direction from its sprints."""
        sprints = await self._stream_sprints(stream_id)
        if not sprints:
            return {"status": "No data", "direction": "steady", "sprint_count": 0}

        snapshots = await self.latest_snapshots_for([s.id for s in sprints])
        bands: list[str] = []
        for sprint in sprints:
            snap = snapshots.get(sprint.id)
            if snap is None:
                continue
            schedule_ahead = bool((snap.factors or {}).get("schedule_ahead", False))
            bands.append(self.value_to_band(snap.confidence_value, schedule_ahead))

        return {
            "status": self._worst_band(bands),
            "direction": await self._stream_direction([s.id for s in sprints]),
            "sprint_count": len(sprints),
        }

    # --- portfolio rollup (executive altitude) ---------------------------

    async def _active_sprint_ids(self) -> list[str]:
        result = await self.db.execute(
            select(Sprint.id).where(Sprint.status == "active")
        )
        return [row[0] for row in result.all()]

    async def get_portfolio_trend(self, days: int = 14) -> list[dict]:
        """Daily mean confidence across ALL active sprints → ``[{date, value}]``.

        Same GROUP BY shape as :meth:`_stream_direction`, but portfolio-wide
        and returning the series itself (the Command Center trend chart) rather
        than a derived slope.
        """
        sprint_ids = await self._active_sprint_ids()
        if not sprint_ids:
            return []
        since = date.today() - timedelta(days=days)
        result = await self.db.execute(
            select(
                ConfidenceSnapshot.snapshot_date,
                func.avg(ConfidenceSnapshot.confidence_value),
            )
            .where(
                ConfidenceSnapshot.sprint_id.in_(sprint_ids),
                ConfidenceSnapshot.snapshot_date >= since,
            )
            .group_by(ConfidenceSnapshot.snapshot_date)
            .order_by(ConfidenceSnapshot.snapshot_date)
        )
        return [
            {"date": row[0].isoformat(), "value": round(float(row[1]), 1)}
            for row in result.all()
        ]

    async def get_portfolio_confidence(self) -> float | None:
        """Mean of the latest snapshot value of every active sprint.

        ``None`` when no active sprint has a snapshot yet (no data ≠ zero).
        """
        snapshots = await self.latest_snapshots_for(await self._active_sprint_ids())
        values = [
            snap.confidence_value
            for snap in snapshots.values()
            if snap.confidence_value is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 1)
