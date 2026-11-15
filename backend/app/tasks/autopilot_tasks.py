"""Celery task for the autopilot control loop.

The beat entry is ALWAYS registered (see celery_app.py); the runtime mode is
read from the DB each tick, which is what makes the off/propose/auto dial
live-togglable. No autoretry — the next tick IS the retry.
"""

import asyncio
import logging

from celery import Task

from app.services.autopilot_service import AutopilotService
from app.tasks.celery_app import celery_app
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)


async def _tick() -> dict:
    async with create_task_session() as session:
        svc = AutopilotService(session)
        state = await svc.get_state()
        if state.get("mode") == "off":
            return {"skipped": "autopilot is off"}
        result = await svc.tick()
        await session.commit()
        return result


@celery_app.task(bind=True)
def autopilot_tick(self: Task) -> dict:
    """Beat-triggered: run one autopilot pass (no-op when mode is off)."""
    return asyncio.run(_tick())
