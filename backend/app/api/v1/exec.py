"""Executive decision queue: every outstanding human decision in one list.

A "decision" is anything still waiting on a human: every ``pending_review``
proposal PLUS approved ``coding_pr`` proposals whose run is still ``pr_open``
(an approved-but-unmerged PR is still an outstanding decision — merging is a
separate deliberate act, mirroring the PRs page's merge gate). Ordering puts
escalations first, then wider scope (portfolio < stream < project), oldest
first within a rank.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_run import AgentRun
from app.models.proposal import Proposal
from app.models.task import Task

router = APIRouter(tags=["executive"])
logger = logging.getLogger(__name__)

# Wider scope outranks narrower scope in the queue (unknown scopes sink last).
_SCOPE_WEIGHT = {"portfolio": 0, "stream": 1, "project": 2}


class DecisionItem(BaseModel):
    """One outstanding decision for the Command Center queue."""

    id: str
    type: str
    state: str
    scope: str
    escalated: bool
    stream_id: str | None = None
    reasoning: str | None = None
    confidence: str | None = None
    created_by_agent: str | None = None
    created_at: datetime | None = None
    summary: str
    # Linked coding run (when the proposal has one).
    run_id: str | None = None
    run_status: str | None = None
    pr_url: str | None = None
    # Linked task (when the proposal content references one).
    task_id: str | None = None
    task_title: str | None = None
    repository: str | None = None


def _summary(proposal: Proposal, run: AgentRun | None, task_title: str | None) -> str:
    """Short per-type human sentence: what is being decided here?"""
    content = proposal.content or {}
    title = task_title or content.get("task_title") or "a task"
    if proposal.type == "coding_pr":
        if proposal.state == "approved":
            return f"Merge the approved AI pull request for '{title}'"
        return f"Review the AI pull request for '{title}'"
    if proposal.type == "autopilot_dispatch":
        return f"Autopilot wants to dispatch '{title}' to the coding agent"
    if proposal.type == "stale_blocker":
        return f"Stale blocker escalated: '{title}' has not moved"
    if proposal.reasoning:
        first_line = proposal.reasoning.strip().splitlines()[0]
        if first_line:
            return first_line[:200]
    return proposal.type.replace("_", " ").capitalize()


@router.get("/decisions", response_model=list[DecisionItem])
async def list_decisions(db: AsyncSession = Depends(get_db)) -> list[DecisionItem]:
    """The unified executive decision queue (see module docstring for the set)."""
    pending = (
        (await db.execute(select(Proposal).where(Proposal.state == "pending_review")))
        .scalars()
        .all()
    )
    # Approved coding PRs that nobody merged yet: still an open decision.
    approved_open_prs = (
        (
            await db.execute(
                select(Proposal)
                .join(AgentRun, AgentRun.proposal_id == Proposal.id)
                .where(
                    Proposal.state == "approved",
                    Proposal.type == "coding_pr",
                    AgentRun.status == "pr_open",
                )
            )
        )
        .scalars()
        .all()
    )
    proposals = [*pending, *approved_open_prs]
    if not proposals:
        return []

    # Batch-join linked runs (by proposal_id) and task titles (by the task the
    # proposal content — or its run — points at). No per-row queries.
    runs_result = await db.execute(
        select(AgentRun).where(AgentRun.proposal_id.in_([p.id for p in proposals]))
    )
    runs_by_proposal = {r.proposal_id: r for r in runs_result.scalars().all()}

    task_ids: set[str] = set()
    for proposal in proposals:
        run = runs_by_proposal.get(proposal.id)
        task_id = (proposal.content or {}).get("task_id") or (run.task_id if run else None)
        if task_id:
            task_ids.add(str(task_id))
    titles: dict[str, str] = {}
    if task_ids:
        titles_result = await db.execute(
            select(Task.id, Task.title).where(Task.id.in_(task_ids))
        )
        titles = {row[0]: row[1] for row in titles_result.all()}

    items: list[DecisionItem] = []
    for proposal in proposals:
        run = runs_by_proposal.get(proposal.id)
        content = proposal.content or {}
        task_id = content.get("task_id") or (run.task_id if run else None)
        task_id = str(task_id) if task_id else None
        task_title = titles.get(task_id) if task_id else None
        items.append(
            DecisionItem(
                id=proposal.id,
                type=proposal.type,
                state=proposal.state,
                scope=proposal.scope,
                escalated=proposal.escalated,
                stream_id=proposal.stream_id,
                reasoning=proposal.reasoning,
                confidence=proposal.confidence,
                created_by_agent=proposal.created_by_agent,
                created_at=proposal.created_at,
                summary=_summary(proposal, run, task_title),
                run_id=run.id if run else None,
                run_status=run.status if run else None,
                pr_url=(run.pr_url if run else None) or content.get("pr_url"),
                task_id=task_id,
                task_title=task_title or content.get("task_title"),
                repository=(run.repository if run else None)
                or content.get("repository"),
            )
        )

    # Escalations first, then wider scope, oldest first within a rank.
    far_future = datetime.max.replace(tzinfo=timezone.utc)
    items.sort(
        key=lambda d: (
            0 if d.escalated else 1,
            _SCOPE_WEIGHT.get(d.scope, len(_SCOPE_WEIGHT)),
            d.created_at or far_future,
        )
    )
    return items
