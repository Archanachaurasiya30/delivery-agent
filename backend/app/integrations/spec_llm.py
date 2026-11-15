"""Groom/triage LLM helpers, shared across coding-agent adapters.

Extracted (by copy) from ``AzureDevOpsCodingAgent.groom``/``triage`` so agents
that don't speak the Pushes API (e.g. the workspace-based Claude Code agent)
can reuse the exact same spec grooming + triage behaviour without inheriting
the Azure adapter. Same prompts, same structured outputs, same graceful
fallbacks: a groom LLM failure degrades to a templated spec and a triage
failure defaults to suitable=True at low confidence — the loop never dies on
LLM flakiness.

The LLM provider is imported lazily so importing this module never needs a key.
"""

import logging

from pydantic import BaseModel

from app.config import settings
from app.integrations.coding_agent import AgentSpec, Suitability

logger = logging.getLogger(__name__)


# ---- Structured LLM outputs -------------------------------------------------
class _GroomOut(BaseModel):
    summary: str
    acceptance: list[str] = []
    target_dirs: list[str] = []
    include_tests: bool = True


class _TriageOut(BaseModel):
    suitable: bool
    reason: str
    confidence: str = "medium"


async def _llm():
    from app.llm.factory import get_llm_provider

    return get_llm_provider()


async def groom_task(task: dict) -> AgentSpec:
    """Turn a raw work item into an executable spec (templated on LLM failure)."""
    try:
        provider = await _llm()
        out = await provider.complete_structured(
            messages=[
                {"role": "system", "content": "You groom delivery work items into executable specs. Be concrete."},
                {"role": "user", "content": (
                    f"Title: {task.get('title')}\nDescription: {task.get('description')}\n"
                    f"Technology: {task.get('technology')}\n"
                    "Produce a build spec: summary, acceptance criteria, target_dirs, include_tests."
                )},
            ],
            response_model=_GroomOut,
        )
        return AgentSpec(
            task_id=str(task["id"]),
            summary=out.summary,
            acceptance=out.acceptance,
            target_dirs=out.target_dirs,
            include_tests=out.include_tests or settings.require_tests,
            notes=task.get("description"),
        )
    except Exception as exc:  # noqa: BLE001 - degrade to a templated spec
        logger.warning("groom LLM failed, using template: %s", exc)
        return AgentSpec(
            task_id=str(task["id"]),
            summary=f"Implement: {task.get('title')}",
            acceptance=["Implements the work item", "Tests added", "CI green"],
            target_dirs=[],
            include_tests=settings.require_tests,
            notes=task.get("description"),
        )


async def triage_spec(task: dict, spec: AgentSpec) -> Suitability:
    """Classify agent-suitability (defaults to suitable at low confidence on failure)."""
    try:
        provider = await _llm()
        out = await provider.complete_structured(
            messages=[
                {"role": "system", "content": "Classify whether a coding agent should attempt this task. Favor well-scoped, low-ambiguity, test-covered work."},
                {"role": "user", "content": f"Spec: {spec.summary}\nAcceptance: {spec.acceptance}"},
            ],
            response_model=_TriageOut,
        )
        conf = out.confidence if out.confidence in ("low", "medium", "high") else "medium"
        return Suitability(suitable=out.suitable, reason=out.reason, confidence=conf)
    except Exception as exc:  # noqa: BLE001
        logger.warning("triage LLM failed, defaulting suitable=True: %s", exc)
        return Suitability(suitable=True, reason="Default triage (LLM unavailable).", confidence="low")
