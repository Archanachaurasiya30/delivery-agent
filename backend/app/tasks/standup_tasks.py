"""Celery tasks for the standup flow: scheduled start, DMs, and analysis."""

import asyncio
import logging

from celery import Task
from sqlalchemy import select

from app.config import settings
from app.integrations.webex_client import WebexClient, WebexRecipientError, can_deliver
from app.models.team import TeamMember
from app.services.standup_service import QUESTIONS, STEPS, StandupService
from app.tasks.celery_app import celery_app
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)

_INTRO = "Good morning! 🌅 Time for your daily standup."


async def _send_question(round_id: str, member_id: str) -> dict:
    async with create_task_session() as session:
        result = await session.execute(
            select(TeamMember).where(TeamMember.id == member_id)
        )
        member = result.scalar_one_or_none()
        if member is None:
            return {"skipped": "no_member"}
        email = member.email

    if not settings.webex_bot_token:
        return {"round_id": round_id, "member_id": member_id, "skipped": "webex_not_configured"}
    if not can_deliver(email):
        # Synthesized by the ADO sync (on-prem gives DOMAIN\\user, not an email).
        return {"round_id": round_id, "member_id": member_id, "skipped": "no_real_email"}
    if settings.app_public_url:
        # Webex can't call back into a LAN deployment, so answers are collected
        # through the in-app form; the DM just carries the personal link.
        link = (
            f"{settings.app_public_url.rstrip('/')}/?standup={round_id}&member={member_id}"
        )
        text = f"{_INTRO}\n\n👉 [Post your update here]({link}) — takes 30 seconds."
    else:
        text = f"{_INTRO}\n\n{QUESTIONS[STEPS[0]]}"
    client = WebexClient(settings.webex_bot_token, base_url=settings.webex_api_base)
    try:
        await client.send_to_email(email, text)
    except WebexRecipientError as exc:
        # Permanent for this member (no Webex account) — don't burn the retries.
        logger.warning("Standup DM skipped for %s: %s", email, exc)
        return {"round_id": round_id, "member_id": member_id, "skipped": "not_on_webex"}
    return {"round_id": round_id, "member_id": member_id, "sent": True}


async def _start(trigger: str) -> dict:
    async with create_task_session() as session:
        service = StandupService(session)
        round_, members = await service.start_round(trigger=trigger)
        round_id = round_.id
        member_ids = [m.id for m in members]

    # Enqueue one DM per member + a hard cutoff to close/analyze the round.
    for member_id in member_ids:
        send_standup_question.delay(round_id, member_id)
    close_standup_round.apply_async(
        args=[round_id], countdown=settings.standup_cutoff_seconds
    )
    return {"round_id": round_id, "members": len(member_ids)}


async def _close(round_id: str) -> dict:
    async with create_task_session() as session:
        service = StandupService(session)
        round_ = await service.close_and_analyze(round_id)
        return {"round_id": round_id, "status": round_.status}


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def send_standup_question(self: Task, round_id: str, member_id: str) -> dict:
    """DM a member the first standup question."""
    return asyncio.run(_send_question(round_id, member_id))


@celery_app.task(bind=True)
def start_scheduled_standup(self: Task) -> dict:
    """Beat-triggered: start a standup round and prompt everyone."""
    logger.info("Starting scheduled standup round")
    return asyncio.run(_start("scheduled"))


@celery_app.task(bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def close_standup_round(self: Task, round_id: str) -> dict:
    """Close collection and analyze (idempotent)."""
    logger.info("Closing standup round %s", round_id)
    return asyncio.run(_close(round_id))
