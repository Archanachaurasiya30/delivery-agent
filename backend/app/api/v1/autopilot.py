"""Autopilot control endpoints: read the dial, flip the dial.

State is DB-backed (app_settings), so a PUT here takes effect on the very next
beat tick — no worker restart. Both endpoints return the same shape: the merged
state + today's counters (incl. the skip audit) + remaining dispatch budget.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.autopilot_service import AutopilotService

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


class AutopilotUpdateRequest(BaseModel):
    """Partial update — only the fields present are changed."""

    mode: str | None = Field(None, pattern="^(off|propose|auto)$")
    daily_limit: int | None = Field(None, ge=0, le=50)
    repository: str | None = None


@router.get("")
async def get_autopilot(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Current state + today's counters + budget_remaining."""
    return await AutopilotService(db).get_status()


@router.put("")
async def update_autopilot(
    req: AutopilotUpdateRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Flip the dial (mode / daily_limit / repository); live on the next tick."""
    svc = AutopilotService(db)
    await svc.update_state(req.model_dump(exclude_unset=True))
    await db.commit()
    return await svc.get_status()
