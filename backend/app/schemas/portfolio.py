"""Schemas for the portfolio (executive) and stream (PM) altitudes."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class StreamSummary(BaseModel):
    """Number-light stream row for the executive portfolio view.

    Deliberately carries NO numeric confidence — the executive altitude shows
    qualitative status/direction only (Phase 1 criterion B).
    """

    id: str
    name: str
    owner_name: str | None = None
    status: str  # On track | At risk | Behind | Ahead | No data
    direction: str  # improving | steady | declining
    sprint_count: int


class EscalationItem(BaseModel):
    """A cross-stream / escalated proposal surfaced only at portfolio level."""

    id: str
    type: str
    scope: str
    escalated: bool
    stream_id: str | None = None
    state: str
    reasoning: str | None = None
    confidence: str | None = None
    created_at: datetime | None = None


class TrendPoint(BaseModel):
    date: date
    value: float


class PortfolioResponse(BaseModel):
    streams: list[StreamSummary]
    escalations: list[EscalationItem]
    # Executive additions (defaulted → additive): the portfolio-wide daily
    # mean confidence series and its latest mean value.
    confidence_trend: list[TrendPoint] = Field(default_factory=list)
    avg_confidence: float | None = None


class ConfidenceFactors(BaseModel):
    scope_remaining: float
    velocity_vs_plan: float
    open_blockers: float
    untested_surface: float


class SprintConfidence(BaseModel):
    """Precise per-sprint release confidence for the PM drill-in (criterion B)."""

    sprint_id: str
    sprint_name: str
    status: str
    confidence_value: float | None = None
    factors: ConfidenceFactors | None = None
    trend: list[TrendPoint] = Field(default_factory=list)


class StreamProposal(BaseModel):
    """Operational (project-scope) proposal in a PM's queue."""

    id: str
    type: str
    state: str
    scope: str
    content: dict[str, Any] | None = None
    reasoning: str | None = None
    confidence: str | None = None
    created_at: datetime | None = None


class StreamDetailResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_name: str | None = None
    status: str
    direction: str
    sprints: list[SprintConfidence]
    proposals: list[StreamProposal]


class StreamListItem(BaseModel):
    id: str
    name: str
