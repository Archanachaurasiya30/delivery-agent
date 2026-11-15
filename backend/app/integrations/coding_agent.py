"""Abstract CodingAgent interface for the pluggable coding-agent PR loop.

Mirrors the TaskProvider pattern (one ABC, swappable implementations behind a
factory, selected by config). The agent's authority ends at "opens a pull
request": a PR is represented as a Proposal, and merge is a separate, explicit
human action — nothing reaches the default branch autonomously.

The target repo can be chosen per dispatch (passed as ``repo`` to run/revise/
get_ci_status/merge); when omitted the adapter falls back to its configured
default repo. The base branch stays config-bound.
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class AgentSpec(BaseModel):
    """A groomed, executable spec derived from a work item."""

    task_id: str
    summary: str
    acceptance: list[str] = []
    target_dirs: list[str] = []
    include_tests: bool = True
    notes: str | None = None


class Suitability(BaseModel):
    """Triage verdict — is this task safe to hand to the agent?"""

    suitable: bool
    reason: str
    confidence: Literal["low", "medium", "high"] = "medium"


class AgentRunResult(BaseModel):
    """Outcome of a run()/revise(): a branch + diff, and a PR once opened."""

    branch_name: str
    diff: str = ""
    diff_lines: int = 0
    pr_id: str | None = None
    pr_url: str | None = None
    cost: float = 0.0
    summary: str = ""
    empty: bool = False


class CIStatus(BaseModel):
    """Normalized CI state for the PR's branch build."""

    state: Literal["pending", "running", "success", "failed", "error", "not_found"]
    build_id: str | None = None
    url: str | None = None


class MergeResult(BaseModel):
    merged: bool
    commit_id: str | None = None
    reason: str | None = None


class CodingAgentError(Exception):
    """Base error for coding-agent operations."""


class GuardrailViolation(CodingAgentError):
    """Raised when a run/diff breaches a configured guardrail."""


class NoRepoConfiguredError(CodingAgentError):
    """Raised when a real adapter has no target repo configured."""


class CodingAgent(ABC):
    """Adapter that turns a work item into a reviewable pull request."""

    @abstractmethod
    async def groom(self, task: dict) -> AgentSpec:
        """Turn a raw work item into an executable spec."""

    @abstractmethod
    async def triage(self, task: dict, spec: AgentSpec) -> Suitability:
        """Classify the task as agent-suitable vs human-only."""

    @abstractmethod
    async def run(
        self, spec: AgentSpec, branch: str, repo: str | None = None
    ) -> AgentRunResult:
        """Generate the change on ``branch`` and open a PR. Never targets main directly.

        ``repo`` is the per-dispatch target repository (name or URL); when None
        the adapter falls back to its configured default repo.
        """

    @abstractmethod
    async def revise(
        self,
        spec: AgentSpec,
        prev: AgentRunResult,
        review_comment: str,
        repo: str | None = None,
    ) -> AgentRunResult:
        """Apply requested changes, updating the SAME PR."""

    @abstractmethod
    async def get_ci_status(
        self, pr_id: str, branch: str, poll_count: int = 0, repo: str | None = None
    ) -> CIStatus:
        """Current CI state for the PR branch. ``poll_count`` lets the mock be deterministic."""

    @abstractmethod
    async def merge(self, pr_id: str, repo: str | None = None) -> MergeResult:
        """Complete/merge the PR — only ever called from the explicit merge action."""
