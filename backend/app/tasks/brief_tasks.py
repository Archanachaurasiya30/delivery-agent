"""Celery tasks for the morning brief: scheduled generation + Webex push.

Same pattern as the standup/confidence tasks — sync Celery task →
``asyncio.run(_worker())`` → per-task ``create_task_session()``. Both tasks run
on the ``default`` queue, i.e. the main worker (which has the GROQ and WEBEX
env). ``generate`` is idempotent per date, so an autoretry after a failed push
re-sends the same brief instead of writing a second one.
"""

import asyncio
import logging

from celery import Task

from app.config import settings
from app.integrations.webex_client import WebexClient
from app.models.brief import Brief
from app.services.brief_service import BriefService
from app.tasks.celery_app import celery_app
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)


def _brief_targets() -> list[str]:
    """Configured brief recipients: room ids and/or person emails."""
    return [t.strip() for t in settings.webex_brief_targets.split(",") if t.strip()]


async def _push_text(text: str) -> dict:
    """Send the brief to every configured target; graceful skip when unset."""
    targets = _brief_targets()
    if not settings.webex_bot_token or not targets:
        return {"pushed": 0, "skipped": "webex not configured"}
    client = WebexClient(settings.webex_bot_token, base_url=settings.webex_api_base)
    for target in targets:
        await client.send(target, text)
    return {"pushed": len(targets)}


async def _generate_and_push() -> dict:
    async with create_task_session() as session:
        brief = await BriefService(session).generate()
        await session.commit()
        brief_id = brief.id
        text = BriefService.to_webex_markdown(brief)
    push = await _push_text(text)
    return {"brief_id": brief_id, **push}


async def _push_brief(brief_id: str) -> dict:
    async with create_task_session() as session:
        brief = await session.get(Brief, brief_id)
        if brief is None:
            return {"brief_id": brief_id, "error": "brief not found"}
        text = BriefService.to_webex_markdown(brief)
    push = await _push_text(text)
    return {"brief_id": brief_id, **push}


@celery_app.task(
    bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True
)
def generate_morning_brief(self: Task) -> dict:
    """Beat-triggered: generate today's brief and push it to Webex inline."""
    logger.info("Generating morning brief")
    return asyncio.run(_generate_and_push())


@celery_app.task(
    bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True
)
def push_brief_to_chat(self: Task, brief_id: str) -> dict:
    """Push an already-generated brief (the synchronous /briefs/generate path)."""
    logger.info("Pushing brief %s to Webex", brief_id)
    return asyncio.run(_push_brief(brief_id))
