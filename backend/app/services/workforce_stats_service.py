"""Workforce stats: aggregate numbers over all coding-agent runs.

Treats the coding agent as an AI workforce and answers the executive
questions — how much did it ship, how fast, at what cost, and what did it save
— for the Command Center stat tiles. Read-only aggregation; nothing here
mutates runs.
"""

import logging
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.agent_run_event import AgentRunEvent
from app.models.task import Task

logger = logging.getLogger(__name__)

# Run statuses that mean "the agent is working right now".
_ACTIVE_STATUSES = ("dispatched", "groomed", "running", "ci_pending")
# Terminal-failure statuses (both count as a failed delivery).
_FAILED_STATUSES = ("failed", "ci_failed")
# Lifecycle event emitted the moment a run's PR goes reviewable (CI green).
_PR_READY_MESSAGE = "PR ready for review"


class WorkforceStatsService:
    """Computes the aggregate AI-workforce stats block."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_stats(self) -> dict:
        by_status = await self._counts_by_status()
        total_runs = sum(by_status.values())
        merged = by_status.get("merged", 0)
        pr_open = by_status.get("pr_open", 0)
        failed = sum(by_status.get(s, 0) for s in _FAILED_STATUSES)
        active_now = sum(by_status.get(s, 0) for s in _ACTIVE_STATUSES)

        # Success rate over finished runs only (in-flight runs are undecided).
        finished = merged + failed
        success_rate = round(merged / finished * 100.0, 1) if finished else None

        total_cost_result = await self.db.execute(
            select(func.coalesce(func.sum(AgentRun.cost_estimate), 0.0))
        )
        total_cost = round(float(total_cost_result.scalar() or 0.0), 2)

        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
        )
        runs_today_result = await self.db.execute(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.created_at >= today_start)
        )
        runs_today = int(runs_today_result.scalar() or 0)

        autopilot_result = await self.db.execute(
            select(func.count())
            .select_from(AgentRun)
            .join(Task, Task.id == AgentRun.task_id)
            .where(
                AgentRun.created_at >= today_start,
                Task.autopilot_state == "dispatched",
            )
        )
        dispatches_today_autopilot = int(autopilot_result.scalar() or 0)

        return {
            "total_runs": total_runs,
            "merged": merged,
            "pr_open": pr_open,
            "failed": failed,
            "active_now": active_now,
            "success_rate": success_rate,
            "total_cost": total_cost,
            "avg_minutes_to_pr": await self._avg_minutes_to_pr(),
            "hours_saved": await self._hours_saved(),
            "runs_today": runs_today,
            "dispatches_today_autopilot": dispatches_today_autopilot,
        }

    # --- pieces -----------------------------------------------------------

    async def _counts_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(AgentRun.status, func.count()).group_by(AgentRun.status)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def _avg_minutes_to_pr(self) -> float | None:
        """Mean minutes from dispatch to the PR going reviewable.

        Primary signal: the first "PR ready for review" lifecycle event of each
        run minus the run's created_at. Fallback for pr_open/merged runs that
        lack the event (older runs predating the event log): updated_at minus
        created_at. ``None`` when no run yields a measurement.
        """
        first_pr_event = (
            select(
                AgentRunEvent.run_id.label("run_id"),
                func.min(AgentRunEvent.created_at).label("pr_at"),
            )
            .where(
                AgentRunEvent.kind == "lifecycle",
                AgentRunEvent.message == _PR_READY_MESSAGE,
            )
            .group_by(AgentRunEvent.run_id)
            .subquery()
        )
        result = await self.db.execute(
            select(AgentRun.id, AgentRun.created_at, first_pr_event.c.pr_at).join(
                first_pr_event, first_pr_event.c.run_id == AgentRun.id
            )
        )
        durations: list[float] = []
        measured_run_ids: set[str] = set()
        for run_id, created_at, pr_at in result.all():
            measured_run_ids.add(run_id)
            if created_at is not None and pr_at is not None and pr_at >= created_at:
                durations.append((pr_at - created_at).total_seconds() / 60.0)

        fallback_result = await self.db.execute(
            select(AgentRun.id, AgentRun.created_at, AgentRun.updated_at).where(
                AgentRun.status.in_(("pr_open", "merged"))
            )
        )
        for run_id, created_at, updated_at in fallback_result.all():
            if run_id in measured_run_ids:
                continue
            if created_at is not None and updated_at is not None and updated_at >= created_at:
                durations.append((updated_at - created_at).total_seconds() / 60.0)

        if not durations:
            return None
        return round(sum(durations) / len(durations), 1)

    async def _hours_saved(self) -> float:
        """Human hours the merged runs' tasks would have cost.

        Per merged run's task: estimated_hours when set, else story_points
        (1 point ≈ 1 hour as the crude proxy), else 0.
        """
        result = await self.db.execute(
            select(Task.estimated_hours, Task.story_points)
            .join(AgentRun, AgentRun.task_id == Task.id)
            .where(AgentRun.status == "merged")
        )
        hours = 0.0
        for estimated_hours, story_points in result.all():
            if estimated_hours is not None:
                hours += float(estimated_hours)
            elif story_points is not None:
                hours += float(story_points)
        return round(hours, 1)
