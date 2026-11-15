"""Celery tasks for the coding-agent PR loop.

Thin glue over ``CodingRunService`` — same pattern as standup/confidence tasks
(sync task → ``asyncio.run(_helper())`` → per-task ``create_task_session()``).
The CI gate lives in ``poll_coding_ci``: a Proposal only reaches ``pending_review``
from the success branch, so a failing CI never surfaces for review.
"""

import asyncio
import logging

from celery import Task
from sqlalchemy import select

from app.config import settings
from app.models.agent_run import AgentRun
from app.services.coding_run_service import CodingRunService
from app.tasks.celery_app import celery_app
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)


async def _dispatch(run_id: str) -> dict:
    poll = False
    status = "failed"
    async with create_task_session() as session:
        svc = CodingRunService(session)
        run = await svc.get_run(run_id)
        try:
            task = await svc.get_task(run)
            spec = await svc.do_groom(run, task)
            suit = await svc.do_triage(run, task, spec)
            if not suit.suitable:
                await session.commit()
                return {"run_id": run_id, "status": run.status}
            await svc.do_run(run, spec)
            poll = run.status == "ci_pending"
            status = run.status
            await session.commit()
        except Exception as exc:  # guardrail/agent/any error → terminal failed
            logger.warning("dispatch failed for run %s: %s", run_id, exc)
            await svc.fail(run, str(exc))
            await session.commit()
            return {"run_id": run_id, "status": "failed", "error": str(exc)}
    if poll:
        poll_coding_ci.delay(run_id)
    return {"run_id": run_id, "status": status}


async def _poll(run_id: str) -> dict:
    requeue = False
    status = "failed"
    async with create_task_session() as session:
        svc = CodingRunService(session)
        run = await svc.get_run(run_id)
        if run.status != "ci_pending":
            return {"run_id": run_id, "status": run.status}
        try:
            outcome = await svc.do_poll_ci(run)
            requeue = outcome == "running"
            status = run.status
            await session.commit()
        except Exception as exc:
            logger.warning("CI poll failed for run %s: %s", run_id, exc)
            await svc.fail(run, str(exc))
            await session.commit()
            return {"run_id": run_id, "status": "failed", "error": str(exc)}
    if requeue:
        poll_coding_ci.apply_async(
            args=[run_id], countdown=settings.coding_agent_ci_poll_interval
        )
    return {"run_id": run_id, "status": status}


async def _revise(run_id: str, comment: str) -> dict:
    requeue = False
    status = "failed"
    async with create_task_session() as session:
        svc = CodingRunService(session)
        run = await svc.get_run(run_id)
        try:
            await svc.do_revise(run, comment)
            requeue = run.status == "ci_pending"
            status = run.status
            await session.commit()
        except Exception as exc:
            logger.warning("revise failed for run %s: %s", run_id, exc)
            await svc.fail(run, str(exc))
            await session.commit()
            return {"run_id": run_id, "status": "failed", "error": str(exc)}
    if requeue:
        poll_coding_ci.delay(run_id)
    return {"run_id": run_id, "status": status}


async def _merge(run_id: str) -> dict:
    async with create_task_session() as session:
        svc = CodingRunService(session)
        run = await svc.get_run(run_id)
        try:
            await svc.do_merge(run)
            await session.commit()
            return {"run_id": run_id, "status": run.status}
        except Exception as exc:
            logger.warning("merge failed for run %s: %s", run_id, exc)
            # Merge guard failures are not run failures — keep the PR reviewable.
            await session.rollback()
            return {"run_id": run_id, "status": run.status, "error": str(exc)}


async def _poll_inflight() -> dict:
    async with create_task_session() as session:
        result = await session.execute(
            select(AgentRun.id).where(AgentRun.status == "ci_pending")
        )
        ids = [row[0] for row in result.all()]
    for rid in ids:
        poll_coding_ci.delay(rid)
    return {"enqueued": len(ids)}


# The in-agent subprocess timeout (claude_code_timeout_seconds, default 1500s)
# fires first for a clean failed run; these per-task limits are the backstop.
@celery_app.task(bind=True, soft_time_limit=1800, time_limit=2100)
def dispatch_coding_agent(self: Task, run_id: str) -> dict:
    """Groom → triage → run on a branch → enqueue first CI poll."""
    return asyncio.run(_dispatch(run_id))


@celery_app.task(bind=True)
def poll_coding_ci(self: Task, run_id: str) -> dict:
    """CI gate: on green register the PR-Proposal; on red park as ci_failed."""
    return asyncio.run(_poll(run_id))


# Same backstop as dispatch: the subprocess timeout fires first, these catch hangs.
@celery_app.task(bind=True, soft_time_limit=1800, time_limit=2100)
def revise_coding_run(self: Task, run_id: str, comment: str) -> dict:
    """Bounded revise loop (iteration cap + cost ceiling)."""
    return asyncio.run(_revise(run_id, comment))


@celery_app.task(bind=True)
def merge_coding_run(self: Task, run_id: str) -> dict:
    """Explicit, human-triggered merge → task done + confidence recompute."""
    return asyncio.run(_merge(run_id))


@celery_app.task(bind=True)
def poll_inflight_coding_ci(self: Task) -> dict:
    """Beat-driven safety net: re-poll any runs stuck in ci_pending."""
    return asyncio.run(_poll_inflight())
