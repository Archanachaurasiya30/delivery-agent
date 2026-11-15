"""Portfolio (executive) endpoint: cross-stream status + escalations.

The executive altitude is deliberately number-light: streams carry qualitative
status/direction only, and the escalations list is the set of proposals that
exceed a single PM (scope in {stream, portfolio}) or are explicitly escalated.
That where-clause is the structural guarantee for Phase 1 criterion A.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.proposal import Proposal
from app.schemas.portfolio import EscalationItem, PortfolioResponse, StreamSummary
from app.services.confidence_service import ConfidenceService
from app.services.stream_service import StreamService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(db: AsyncSession = Depends(get_db)) -> PortfolioResponse:
    """Streams with derived qualitative status/direction + the escalations list."""
    stream_service = StreamService(db)
    confidence = ConfidenceService(db)

    streams = await stream_service.list_streams()
    owners = await stream_service.owner_names()

    summaries: list[StreamSummary] = []
    for stream in streams:
        rollup = await confidence.get_stream_rollup(stream.id)
        summaries.append(
            StreamSummary(
                id=stream.id,
                name=stream.name,
                owner_name=owners.get(stream.owner_id) if stream.owner_id else None,
                status=rollup["status"],
                direction=rollup["direction"],
                sprint_count=rollup["sprint_count"],
            )
        )

    # Escalations: above a single PM's altitude. This filter is the structural
    # reason cross-stream/escalated proposals surface ONLY here and never in a
    # stream's operational queue (criterion A).
    result = await db.execute(
        select(Proposal)
        .where(
            or_(
                Proposal.scope.in_(["stream", "portfolio"]),
                Proposal.escalated.is_(True),
            )
        )
        .order_by(Proposal.created_at.desc())
    )
    escalations = [
        EscalationItem(
            id=p.id,
            type=p.type,
            scope=p.scope,
            escalated=p.escalated,
            stream_id=p.stream_id,
            state=p.state,
            reasoning=p.reasoning,
            confidence=p.confidence,
            created_at=p.created_at,
        )
        for p in result.scalars().all()
    ]

    return PortfolioResponse(
        streams=summaries,
        escalations=escalations,
        confidence_trend=await confidence.get_portfolio_trend(),
        avg_confidence=await confidence.get_portfolio_confidence(),
    )
