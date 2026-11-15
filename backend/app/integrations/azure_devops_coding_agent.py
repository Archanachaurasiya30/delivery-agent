"""Real CodingAgent backed by Azure DevOps (Azure Repos + Azure Pipelines).

Reuses the PAT -> ``base64(":"+pat)`` Basic auth + ``httpx.AsyncClient`` pattern
from ``TFSTaskProvider`` against the Azure DevOps REST API (api-version 7.1).

Flow per ``run``:
  1. LLM produces structured file changes (path + new content) for the spec.
  2. Azure Repos **Pushes API** creates the feature branch off the default
     branch with those changes (no local checkout needed).
  3. Azure Repos **Pull Requests API** opens a PR (source feature branch ->
     target default branch). The agent never pushes to the default branch.
  4. ``get_ci_status`` polls **Azure Pipelines Builds** for that branch.
  5. ``merge`` completes the PR (explicit, human-triggered only).

This adapter requires real Azure credentials + repo config and an LLM key; it is
lazily imported by the factory so the mock demo never needs any of it.
"""

import base64
import logging

import httpx
from pydantic import BaseModel

from app.config import settings
from app.integrations.coding_agent import (
    AgentRunResult,
    AgentSpec,
    CIStatus,
    CodingAgent,
    CodingAgentError,
    MergeResult,
    NoRepoConfiguredError,
    Suitability,
)

logger = logging.getLogger(__name__)

API_VERSION = "7.1"


# ---- Structured LLM outputs -------------------------------------------------
class _FileChange(BaseModel):
    path: str  # repo-relative, no leading slash
    content: str
    change_type: str = "edit"  # "add" | "edit"


class _Changeset(BaseModel):
    commit_message: str
    changes: list[_FileChange] = []


class _GroomOut(BaseModel):
    summary: str
    acceptance: list[str] = []
    target_dirs: list[str] = []
    include_tests: bool = True


class _TriageOut(BaseModel):
    suitable: bool
    reason: str
    confidence: str = "medium"


class AzureDevOpsCodingAgent(CodingAgent):
    def __init__(
        self,
        org_url: str,
        project: str,
        repo_id: str,
        pat: str,
        default_branch: str = "main",
        pipeline_id: str = "",
        timeout: float = 60.0,
    ) -> None:
        if not (org_url and project and repo_id):
            raise NoRepoConfiguredError(
                "Azure coding agent needs tfs_url + azure_repo_project + azure_repo_id."
            )
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.repo_id = repo_id
        self.default_branch = default_branch
        self.pipeline_id = pipeline_id
        self.timeout = timeout
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._auth_header = f"Basic {token}"

    # ---- HTTP plumbing (mirrors TFSTaskProvider) ----
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout, headers={"Authorization": self._auth_header}
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise CodingAgentError(
                f"Azure DevOps API error {resp.status_code}: {resp.text[:500]}"
            )

    def _git(self, path: str, repo_id: str | None = None) -> str:
        repo = repo_id or self.repo_id
        return f"{self.org_url}/{self.project}/_apis/git/repositories/{repo}/{path}"

    # ---- LLM helpers (lazy import so import never needs an LLM key) ----
    async def _llm(self):
        from app.llm.factory import get_llm_provider

        return get_llm_provider()

    # ---- CodingAgent interface ----
    async def groom(self, task: dict) -> AgentSpec:
        try:
            provider = await self._llm()
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

    async def triage(self, task: dict, spec: AgentSpec) -> Suitability:
        try:
            provider = await self._llm()
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

    async def _generate_changeset(self, spec: AgentSpec, prior: str | None = None) -> _Changeset:
        provider = await self._llm()
        instruction = (
            f"Implement this spec as concrete file changes for an Azure Repos push.\n"
            f"Spec: {spec.summary}\nAcceptance: {spec.acceptance}\n"
            f"Target dirs: {spec.target_dirs}\nInclude tests: {spec.include_tests}\n"
        )
        if prior:
            instruction += f"\nApply this review feedback to your previous attempt: {prior}\n"
        return await provider.complete_structured(
            messages=[
                {"role": "system", "content": "You write minimal, correct, well-tested diffs. Output full file contents for each changed file."},
                {"role": "user", "content": instruction},
            ],
            response_model=_Changeset,
        )

    @staticmethod
    def _render_diff(changeset: _Changeset) -> tuple[str, int]:
        """Render a unified-diff-ish string + count added lines (for display + guardrails)."""
        parts: list[str] = []
        added = 0
        for ch in changeset.changes:
            parts.append(f"diff --git a/{ch.path} b/{ch.path}")
            parts.append(f"+++ b/{ch.path}")
            for line in ch.content.splitlines():
                parts.append(f"+{line}")
                added += 1
        return "\n".join(parts), added

    async def _base_object_id(self, client: httpx.AsyncClient, repo_id: str | None = None) -> str:
        url = self._git(f"refs?filter=heads/{self.default_branch}&api-version={API_VERSION}", repo_id)
        resp = await client.get(url)
        self._raise_for_status(resp)
        refs = resp.json().get("value", [])
        if not refs:
            raise CodingAgentError(f"Default branch '{self.default_branch}' not found.")
        return refs[0]["objectId"]

    async def _push_branch(
        self, client: httpx.AsyncClient, branch: str, changeset: _Changeset, repo_id: str | None = None
    ) -> None:
        base = await self._base_object_id(client, repo_id)
        body = {
            "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": base}],
            "commits": [{
                "comment": changeset.commit_message or "agent change",
                "changes": [
                    {
                        "changeType": ch.change_type,
                        "item": {"path": "/" + ch.path.lstrip("/")},
                        "newContent": {"content": ch.content, "contentType": "rawtext"},
                    }
                    for ch in changeset.changes
                ],
            }],
        }
        resp = await client.post(self._git(f"pushes?api-version={API_VERSION}", repo_id), json=body)
        self._raise_for_status(resp)

    async def _open_pr(
        self, client: httpx.AsyncClient, branch: str, spec: AgentSpec, repo_id: str | None = None
    ) -> tuple[str, str]:
        repo = repo_id or self.repo_id
        body = {
            "sourceRefName": f"refs/heads/{branch}",
            "targetRefName": f"refs/heads/{self.default_branch}",
            "title": spec.summary[:200],
            "description": "Opened by the delivery coding agent. Review before merge.",
        }
        resp = await client.post(self._git(f"pullrequests?api-version={API_VERSION}", repo_id), json=body)
        self._raise_for_status(resp)
        pr = resp.json()
        pr_id = str(pr["pullRequestId"])
        pr_url = f"{self.org_url}/{self.project}/_git/{repo}/pullrequest/{pr_id}"
        return pr_id, pr_url

    async def run(self, spec: AgentSpec, branch: str, repo: str | None = None) -> AgentRunResult:
        repo_id = repo or self.repo_id
        changeset = await self._generate_changeset(spec)
        if not changeset.changes:
            return AgentRunResult(branch_name=branch, empty=True, summary="Agent produced no changes.")
        diff, added = self._render_diff(changeset)
        async with self._client() as client:
            await self._push_branch(client, branch, changeset, repo_id)
            pr_id, pr_url = await self._open_pr(client, branch, spec, repo_id)
        return AgentRunResult(
            branch_name=branch, diff=diff, diff_lines=added,
            pr_id=pr_id, pr_url=pr_url, cost=0.5, summary=changeset.commit_message,
        )

    async def revise(
        self, spec: AgentSpec, prev: AgentRunResult, review_comment: str, repo: str | None = None
    ) -> AgentRunResult:
        repo_id = repo or self.repo_id
        changeset = await self._generate_changeset(spec, prior=review_comment)
        if not changeset.changes:
            return AgentRunResult(branch_name=prev.branch_name, pr_id=prev.pr_id, pr_url=prev.pr_url, empty=True)
        diff, added = self._render_diff(changeset)
        async with self._client() as client:
            await self._push_branch(client, prev.branch_name, changeset, repo_id)
        return AgentRunResult(
            branch_name=prev.branch_name, diff=diff, diff_lines=added,
            pr_id=prev.pr_id, pr_url=prev.pr_url, cost=0.5,
            summary=f"Revised: {changeset.commit_message}",
        )

    async def get_ci_status(
        self, pr_id: str, branch: str, poll_count: int = 0, repo: str | None = None
    ) -> CIStatus:
        if not self.pipeline_id:
            # No pipeline configured → nothing to gate on; treat as success.
            return CIStatus(state="success")
        url = (
            f"{self.org_url}/{self.project}/_apis/build/builds"
            f"?definitions={self.pipeline_id}&branchName=refs/heads/{branch}"
            f"&$top=1&api-version={API_VERSION}"
        )
        async with self._client() as client:
            resp = await client.get(url)
            self._raise_for_status(resp)
            builds = resp.json().get("value", [])
        if not builds:
            return CIStatus(state="not_found")
        build = builds[0]
        status, result = build.get("status"), build.get("result")
        if status != "completed":
            return CIStatus(state="running", build_id=str(build.get("id")), url=build.get("_links", {}).get("web", {}).get("href"))
        state = "success" if result == "succeeded" else "failed"
        return CIStatus(state=state, build_id=str(build.get("id")), url=build.get("_links", {}).get("web", {}).get("href"))

    async def merge(self, pr_id: str, repo: str | None = None) -> MergeResult:
        repo_id = repo or self.repo_id
        async with self._client() as client:
            # Fetch the PR for its last source commit (required to complete).
            get = await client.get(self._git(f"pullrequests/{pr_id}?api-version={API_VERSION}", repo_id))
            self._raise_for_status(get)
            pr = get.json()
            last_commit = pr.get("lastMergeSourceCommit")
            body = {
                "status": "completed",
                "lastMergeSourceCommit": last_commit,
                "completionOptions": {"mergeStrategy": "squash", "deleteSourceBranch": True},
            }
            patch = await client.patch(self._git(f"pullrequests/{pr_id}?api-version={API_VERSION}", repo_id), json=body)
            self._raise_for_status(patch)
            merged = patch.json()
        return MergeResult(
            merged=merged.get("status") == "completed",
            commit_id=(merged.get("lastMergeCommit") or {}).get("commitId"),
        )
