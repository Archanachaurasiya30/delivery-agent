"""Celery task: daily release-confidence snapshot for active sprints.

Mirrors the standup task pattern — a module-level async worker bridged to Celery
via ``asyncio.run`` with its own per-task session. Persisting a daily snapshot
per active sprint is what turns confidence into a queryable trend (Phase 1
criterion C). The upsert in ``snapshot_sprint`` makes re-runs idempotent.
"""

import asyncio
import logging

from celery import Task
from sqlalchemy import select

from app.models.sprint import Sprint
from app.services.confidence_service import ConfidenceService
from app.tasks.celery_app import celery_app
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)


async def _snapshot_all() -> dict:
    async with create_task_session() as session:
        result = await session.execute(
            select(Sprint).where(Sprint.status == "active")
        )
        sprints = list(result.scalars().all())

        service = ConfidenceService(session)
        snapshotted = 0
        for sprint in sprints:
            snap = await service.snapshot_sprint(sprint.id)
            if snap is not None:
                snapshotted += 1
        await session.commit()

    return {"active_sprints": len(sprints), "snapshotted": snapshotted}


@celery_app.task(
    bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True
)
def snapshot_active_sprints(self: Task) -> dict:
    """Beat-triggered: upsert today's confidence snapshot per active sprint."""
    logger.info("Snapshotting confidence for active sprints")
    return asyncio.run(_snapshot_all())
