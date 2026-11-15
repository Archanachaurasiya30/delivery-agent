"""Stream (PM) endpoints: nav list + drill-in with confidence + operational queue.

The PM altitude shows precise numbers (per-sprint confidence value, factors, and
the daily trend series) and an operational queue restricted to project-scope
proposals for this stream. Escalated/portfolio proposals are excluded here by
construction and live only in /portfolio (criterion A & B).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.proposal import Proposal
from app.schemas.portfolio import (
    SprintConfidence,
    StreamDetailResponse,
    StreamListItem,
    StreamProposal,
)
from app.services.confidence_service import ConfidenceService
from app.services.stream_service import StreamService

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("", response_model=list[StreamListItem])
async def list_streams(db: AsyncSession = Depends(get_db)) -> list[StreamListItem]:
    """Lightweight stream list for navigation."""
    service = StreamService(db)
    streams = await service.list_streams()
    return [StreamListItem(id=s.id, name=s.name) for s in streams]


@router.get("/{stream_id}", response_model=StreamDetailResponse)
async def get_stream_detail(
    stream_id: str, db: AsyncSession = Depends(get_db)
) -> StreamDetailResponse:
    """Drill-in: per-sprint confidence (value + factors + trend) + operational queue."""
    stream_service = StreamService(db)
    confidence = ConfidenceService(db)

    stream = await stream_service.get_stream(stream_id)
    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stream not found: {stream_id}",
        )

    owners = await stream_service.owner_names()
    rollup = await confidence.get_stream_rollup(stream_id)

    sprints = await stream_service.get_stream_sprints(stream_id)
    sprint_confidences = [
        SprintConfidence(**(await confidence.get_sprint_confidence(sprint)))
        for sprint in sprints
    ]

    # Operational queue: ONLY project-scope proposals for THIS stream.
    result = await db.execute(
        select(Proposal)
        .where(Proposal.stream_id == stream_id, Proposal.scope == "project")
        .order_by(Proposal.created_at.desc())
    )
    proposals = [
        StreamProposal(
            id=p.id,
            type=p.type,
            state=p.state,
            scope=p.scope,
            content=p.content,
            reasoning=p.reasoning,
            confidence=p.confidence,
            created_at=p.created_at,
        )
        for p in result.scalars().all()
    ]

    return StreamDetailResponse(
        id=stream.id,
        name=stream.name,
        description=stream.description,
        owner_name=owners.get(stream.owner_id) if stream.owner_id else None,
        status=rollup["status"],
        direction=rollup["direction"],
        sprints=sprint_confidences,
        proposals=proposals,
    )
