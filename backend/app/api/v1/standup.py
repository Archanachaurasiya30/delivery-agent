"""Standup API: trigger rounds, inspect results, link Telegram accounts."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.team import TeamMember
from app.services.standup_service import StandupService

router = APIRouter(prefix="/standup", tags=["standup"])


class StartRoundResponse(BaseModel):
    round_id: str
    expected_count: int


class LinkCodeResponse(BaseModel):
    code: str
    deep_link: str | None = None


class SubmitEntryRequest(BaseModel):
    member_id: str
    yesterday: str = Field(..., min_length=1)
    today: str = Field(..., min_length=1)
    blockers: str | None = None


async def _member_names(db: AsyncSession, entries: list) -> dict[str, str]:
    ids = [e.member_id for e in entries]
    if not ids:
        return {}
    rows = await db.execute(select(TeamMember.id, TeamMember.name).where(TeamMember.id.in_(ids)))
    return {r[0]: r[1] for r in rows.all()}


def _round_to_dict(round_, entries: list, names: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": round_.id,
        "status": round_.status,
        "trigger": round_.trigger,
        "expected_count": round_.expected_count,
        "proposal_id": round_.proposal_id,
        "summary": round_.summary,
        "created_at": round_.created_at,
        "closed_at": round_.closed_at,
        "entries": [
            {
                "member_id": e.member_id,
                "member_name": (names or {}).get(e.member_id),
                "yesterday": e.yesterday,
                "today": e.today,
                "blockers": e.blockers,
                "completed": e.completed,
                "submitted_at": e.submitted_at,
            }
            for e in entries
        ],
    }


@router.post("/start", response_model=StartRoundResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_standup(db: AsyncSession = Depends(get_db)) -> StartRoundResponse:
    """Start a manual standup round and DM each linked member."""
    from app.tasks.standup_tasks import close_standup_round, send_standup_question

    service = StandupService(db)
    round_, members = await service.start_round(trigger="manual")

    for member in members:
        send_standup_question.delay(round_.id, member.id)
    close_standup_round.apply_async(
        args=[round_.id], countdown=settings.standup_cutoff_seconds
    )
    return StartRoundResponse(round_id=round_.id, expected_count=len(members))


@router.get("/rounds")
async def list_rounds(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    service = StandupService(db)
    rounds = await service.list_rounds()
    out = []
    for r in rounds:
        entries = await service.get_entries(r.id)
        out.append(_round_to_dict(r, entries))
    return out


@router.get("/rounds/{round_id}")
async def get_round(round_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    service = StandupService(db)
    round_ = await service.get_round(round_id)
    if round_ is None:
        raise HTTPException(status_code=404, detail="Standup round not found")
    entries = await service.get_entries(round_.id)
    return _round_to_dict(round_, entries, await _member_names(db, entries))


@router.post("/rounds/{round_id}/entries")
async def submit_entry(
    round_id: UUID, body: SubmitEntryRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Answer the standup from the web form (the link in the Webex DM)."""
    from app.tasks.standup_tasks import close_standup_round

    try:
        complete = await StandupService(db).submit_entry(
            str(round_id), body.member_id, body.yesterday, body.today, body.blockers
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if complete:
        close_standup_round.delay(str(round_id))
    return {"recorded": True, "round_complete": complete}


@router.post("/rounds/{round_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def close_round(round_id: UUID) -> dict[str, str]:
    """Force-close + analyze a round now (don't wait for the cutoff)."""
    from app.tasks.standup_tasks import close_standup_round

    close_standup_round.delay(str(round_id))
    return {"status": "closing", "round_id": str(round_id)}


@router.post("/link-code/{member_id}", response_model=LinkCodeResponse)
async def create_link_code(
    member_id: UUID, db: AsyncSession = Depends(get_db)
) -> LinkCodeResponse:
    """Generate a one-time code a member sends to the bot as /start <code>."""
    service = StandupService(db)
    code = await service.create_link_code(member_id)
    deep_link = (
        f"https://t.me/{settings.telegram_bot_username}?start={code}"
        if settings.telegram_bot_username
        else None
    )
    return LinkCodeResponse(code=code, deep_link=deep_link)
