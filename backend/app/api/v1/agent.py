"""Agent API endpoints for async agent requests."""

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.proposal import Proposal
from app.services import proposal_executor
from app.services.agent_analysis_service import AgentAnalysisService
from app.services.ask_service import AskService
from app.services.groq_client import GroqError
from app.tasks.agent_tasks import process_agent_request

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


# Request/Response schemas
class AgentRequest(BaseModel):
    """Request body for agent processing."""

    type: str = Field(..., description="Type of agent request (e.g., 'echo', 'sprint_planning')")
    payload: dict[str, Any] = Field(default_factory=dict, description="Request payload data")


class AgentRequestResponse(BaseModel):
    """Response for submitted agent request."""

    proposal_id: str = Field(..., description="UUID of the created proposal")
    status: str = Field(..., description="Current processing status")


class ProposalResponse(BaseModel):
    """Response containing proposal details."""

    id: str
    type: str
    state: str
    content: dict[str, Any] | None
    reasoning: str | None
    confidence: str | None
    created_by_agent: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    execution_result: dict[str, Any] | None = None


class ApproveRejectRequest(BaseModel):
    """Request body for approve/reject actions."""

    reason: str | None = Field(None, description="Optional reason for the action")


class CreateProposalRequest(BaseModel):
    """Request body for persisting a finished agent analysis as a proposal."""

    type: str = Field(..., description="Proposal type, e.g. sprint_planning / blocker_detection")
    content: dict[str, Any] | None = Field(None, description="Structured proposal content")
    reasoning: str | None = Field(None, description="Human-readable summary / reasoning")
    confidence: str | None = Field(None, description="low / medium / high")
    created_by_agent: str | None = Field(None, description="Identifier of the generating agent")


class AnalyzeRequest(BaseModel):
    """Request body for synchronous AI analysis."""

    prompt: str = Field(..., description="The prompt to analyze")
    system_prompt: str | None = Field(
        None,
        description="Optional system prompt override"
    )


class AnalyzeResponse(BaseModel):
    """Response from AI analysis."""

    content: str = Field(..., description="AI generated response")
    model: str = Field(..., description="Model used for analysis")


class AskMessage(BaseModel):
    """One prior turn of the Ask-the-Delivery-Manager conversation."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class AskRequest(BaseModel):
    """Request body for Ask the Delivery Manager."""

    question: str = Field(..., min_length=1, description="The question to answer")
    history: list[AskMessage] = Field(
        default_factory=list,
        description="Prior conversation turns (only the last few are used)",
    )


class AskResponse(BaseModel):
    """Answer from the delivery manager over the live-data snapshot."""

    answer: str = Field(..., description="Plain-text answer")
    generated_at: datetime = Field(..., description="When the answer was generated")


def _reviewer(header_value: str | None) -> str:
    """Who approved/rejected. There is no login on the LAN deployment, so the
    UI asks for a name once and sends it as ``X-User-Name``."""
    name = unquote(header_value or "").strip()  # UI URL-encodes (headers are ASCII)
    return name[:100] if name else "unknown"


ANALYSES = {"sprint_planning", "blocker_detection", "release_management"}


@router.post("/analysis/{kind}")
async def run_analysis(
    kind: str,
    sprint_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run one agent analysis over the live (synced) delivery data.

    Facts come from the database; the LLM adds ranking and suggested actions.
    The result is saved as a ``pending_review`` proposal and returned.
    """
    if kind not in ANALYSES:
        raise HTTPException(status_code=404, detail=f"Unknown analysis: {kind}")
    service = AgentAnalysisService(db)
    try:
        if kind == "sprint_planning":
            return await service.plan_sprint()
        if kind == "blocker_detection":
            return await service.detect_blockers()
        return await service.assess_release(sprint_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/request",
    response_model=AgentRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_agent_request(
    request: AgentRequest,
    db: AsyncSession = Depends(get_db),
) -> AgentRequestResponse:
    """
    Submit an agent request for async processing.

    Creates a proposal record and queues the request for background processing.
    Returns immediately with 202 Accepted - the proposal is processed asynchronously.

    Args:
        request: Agent request with type and payload.
        db: Database session.

    Returns:
        Response with proposal_id and initial status.
    """
    logger.info(f"Received agent request: type={request.type}")

    # Create proposal record
    proposal = Proposal(
        type=request.type,
        state="draft",
        content={"request_payload": request.payload},
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    proposal_id = str(proposal.id)
    logger.info(f"Created proposal: {proposal_id}")

    # Queue background task
    process_agent_request.delay(
        proposal_id=proposal_id,
        request_type=request.type,
        payload=request.payload,
    )
    logger.info(f"Queued agent task for proposal: {proposal_id}")

    return AgentRequestResponse(
        proposal_id=proposal_id,
        status="processing",
    )


@router.post(
    "/proposals",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    request: CreateProposalRequest,
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Persist a finished agent analysis as a proposal.

    Used by the frontend agent screen to save the report it generated (sprint
    planning, blocker detection, release assessment, standup) so it survives a
    reload and shows up in the Proposals review queue in ``pending_review``.
    """
    proposal = Proposal(
        type=request.type,
        state="pending_review",
        content=request.content,
        reasoning=request.reasoning,
        confidence=request.confidence,
        created_by_agent=request.created_by_agent or "frontend-agent",
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    logger.info(f"Created proposal from agent analysis: {proposal.id} ({proposal.type})")

    return ProposalResponse(
        id=str(proposal.id),
        type=proposal.type,
        state=proposal.state,
        content=proposal.content,
        reasoning=proposal.reasoning,
        confidence=proposal.confidence,
        created_by_agent=proposal.created_by_agent,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        execution_result=proposal.execution_result,
    )


@router.get(
    "/proposals",
    response_model=list[ProposalResponse],
)
async def list_proposals(
    state: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[ProposalResponse]:
    """
    List all proposals, optionally filtered by state.

    Args:
        state: Filter by proposal state (draft, pending_review, approved, rejected).
        limit: Maximum number of proposals to return.
        db: Database session.

    Returns:
        List of proposals.
    """
    query = select(Proposal)
    if state:
        query = query.where(Proposal.state == state)
    query = query.order_by(Proposal.created_at.desc()).limit(limit)

    result = await db.execute(query)
    proposals = result.scalars().all()

    return [
        ProposalResponse(
            id=str(p.id),
            type=p.type,
            state=p.state,
            content=p.content,
            reasoning=p.reasoning,
            confidence=p.confidence,
            created_by_agent=p.created_by_agent,
            reviewed_by=p.reviewed_by,
            reviewed_at=p.reviewed_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
            execution_result=p.execution_result,
        )
        for p in proposals
    ]


@router.get(
    "/proposals/{proposal_id}",
    response_model=ProposalResponse,
)
async def get_proposal(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Get proposal by ID.

    Args:
        proposal_id: UUID of the proposal.
        db: Database session.

    Returns:
        Proposal details.

    Raises:
        HTTPException: If proposal not found.
    """
    result = await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()

    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal not found: {proposal_id}",
        )

    return ProposalResponse(
        id=str(proposal.id),
        type=proposal.type,
        state=proposal.state,
        content=proposal.content,
        reasoning=proposal.reasoning,
        confidence=proposal.confidence,
        created_by_agent=proposal.created_by_agent,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        execution_result=proposal.execution_result,
    )


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ProposalResponse,
)
async def approve_proposal(
    proposal_id: UUID,
    request: ApproveRejectRequest | None = None,
    x_user_name: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Approve a proposal.

    Transitions proposal from pending_review to approved state.

    Args:
        proposal_id: UUID of the proposal.
        request: Optional approval reason.
        db: Database session.

    Returns:
        Updated proposal details.

    Raises:
        HTTPException: If proposal not found or in invalid state.
    """
    result = await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()

    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal not found: {proposal_id}",
        )

    if proposal.state != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve proposal in state: {proposal.state}. "
                   f"Expected: pending_review",
        )

    proposal.state = "approved"
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.reviewed_by = _reviewer(x_user_name)

    if request and request.reason:
        proposal.execution_result = {
            **(proposal.execution_result or {}), "approval_reason": request.reason,
        }

    # Approval does something: notify blocker owners / produce the ADO checklist.
    await proposal_executor.execute(proposal, proposal.reviewed_by)

    await db.commit()
    await db.refresh(proposal)

    logger.info(f"Approved proposal: {proposal_id}")

    return ProposalResponse(
        id=str(proposal.id),
        type=proposal.type,
        state=proposal.state,
        content=proposal.content,
        reasoning=proposal.reasoning,
        confidence=proposal.confidence,
        created_by_agent=proposal.created_by_agent,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        execution_result=proposal.execution_result,
    )


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ProposalResponse,
)
async def reject_proposal(
    proposal_id: UUID,
    request: ApproveRejectRequest,
    x_user_name: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Reject a proposal.

    Transitions proposal from pending_review to rejected state.

    Args:
        proposal_id: UUID of the proposal.
        request: Rejection reason (required).
        db: Database session.

    Returns:
        Updated proposal details.

    Raises:
        HTTPException: If proposal not found or in invalid state.
    """
    result = await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()

    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal not found: {proposal_id}",
        )

    if proposal.state != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject proposal in state: {proposal.state}. "
                   f"Expected: pending_review",
        )

    proposal.state = "rejected"
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.reviewed_by = _reviewer(x_user_name)

    proposal.execution_result = {
        **(proposal.execution_result or {}),
        "rejection_reason": request.reason or "No reason provided",
    }

    await db.commit()
    await db.refresh(proposal)

    logger.info(f"Rejected proposal: {proposal_id}")

    return ProposalResponse(
        id=str(proposal.id),
        type=proposal.type,
        state=proposal.state,
        content=proposal.content,
        reasoning=proposal.reasoning,
        confidence=proposal.confidence,
        created_by_agent=proposal.created_by_agent,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        execution_result=proposal.execution_result,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
)
async def analyze_with_ai(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Perform synchronous AI analysis using Groq.

    This endpoint is used by the frontend for real-time AI analysis
    of team data, blockers, sprint planning, and release assessment.

    Args:
        request: Analysis request with prompt and optional system prompt.

    Returns:
        AI generated response content.

    Raises:
        HTTPException: If Groq API key not configured or API call fails.
    """
    print(f"🤖 [AGENT] /analyze endpoint called")
    print(f"🤖 [AGENT] Prompt length: {len(request.prompt)} chars")
    print(f"🤖 [AGENT] GROQ_API_KEY set: {bool(settings.groq_api_key)}")
    print(f"🤖 [AGENT] GROQ_MODEL: {settings.groq_model}")

    if not settings.groq_api_key:
        print("❌ [AGENT] No GROQ_API_KEY configured!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Set GROQ_API_KEY environment variable.",
        )

    model = settings.groq_model
    logger.info(f"AI analysis request using model: {model}")

    system_prompt = request.system_prompt or (
        "You are an AI delivery manager assistant. Analyze team data and provide "
        "actionable insights. Be concise and structured. Focus on blockers, risks, "
        "and recommendations. Always return valid JSON when asked."
    )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.prompt},
        ],
        "temperature": 0.7,
        "max_tokens": settings.groq_max_tokens,
    }
    # gpt-oss reasoning models accept reasoning_effort; sending it to a
    # non-reasoning model would be rejected, so only attach it for those.
    if "gpt-oss" in model:
        payload["reasoning_effort"] = settings.groq_reasoning_effort

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.groq_api_key}",
                },
                json=payload,
            )

            print(f"🤖 [AGENT] Groq response status: {response.status_code}")

            if response.status_code != 200:
                error_detail = response.json().get("error", {}).get("message", "Unknown error")
                print(f"❌ [AGENT] Groq API error: {response.status_code} - {error_detail}")
                logger.error(f"Groq API error: {response.status_code} - {error_detail}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Groq API error: {error_detail}",
                )

            data = response.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            finish_reason = choice.get("finish_reason")

            # A reasoning model can exhaust max_tokens on reasoning and return
            # empty/truncated content with finish_reason="length". Surface that
            # as an error instead of a misleading 200 with no JSON to parse.
            if not content.strip():
                print(
                    f"❌ [AGENT] Empty content from model (finish_reason={finish_reason})"
                )
                logger.error(
                    f"Groq returned empty content (finish_reason={finish_reason})"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "AI returned an empty response "
                        f"(finish_reason={finish_reason}). The model likely ran out "
                        "of token budget; try a shorter prompt or raise GROQ_MAX_TOKENS."
                    ),
                )

            if finish_reason == "length":
                print(f"⚠️ [AGENT] Response truncated (finish_reason=length)")
                logger.warning("Groq response truncated (finish_reason=length)")

            print(f"✅ [AGENT] AI analysis success! Response length: {len(content)} chars")
            logger.info("AI analysis completed successfully")
            return AnalyzeResponse(content=content, model=model)

    except httpx.TimeoutException:
        print("❌ [AGENT] Groq API request timed out!")
        logger.error("Groq API request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI analysis request timed out",
        )
    except httpx.RequestError as e:
        print(f"❌ [AGENT] Groq API request failed: {e}")
        logger.error(f"Groq API request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to AI service: {str(e)}",
        )


@router.post(
    "/ask",
    response_model=AskResponse,
)
async def ask_delivery_manager(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
) -> AskResponse:
    """
    Ask the AI delivery manager a question over live delivery data.

    The server assembles a fresh snapshot (streams, confidence, sprint, AI
    workforce, standup, pending decisions) per question — the model answers
    ONLY from that data. Error mapping mirrors /analyze.
    """
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Set GROQ_API_KEY environment variable.",
        )

    try:
        answer = await AskService(db).answer(
            request.question, [m.model_dump() for m in request.history]
        )
    except GroqError as e:
        logger.error(f"Ask-the-DM failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {e}",
        )

    return AskResponse(answer=answer, generated_at=datetime.now(timezone.utc))
