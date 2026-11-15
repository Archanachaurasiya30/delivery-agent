"""Deterministic, in-process CodingAgent for local demos and tests.

No git, no network, no randomness/clock — every value derives from the task id
and config, so the whole loop is reproducible. The synthetic diff is built to
honor the guardrails (touches only the target dir, includes a test file, stays
tiny), so the happy path sails through; guardrail breaches are exercised by
forcing config (small caps, ``mock_ci_fail_first``).
"""

import hashlib

from app.config import settings
from app.integrations.coding_agent import (
    AgentRunResult,
    AgentSpec,
    CIStatus,
    CodingAgent,
    MergeResult,
    Suitability,
)

# Map a technology to a plausible source dir for the synthetic diff.
_TECH_DIR = {
    ".NET": "src/dotnet",
    "Android": "android/app",
    "iOS": "ios/App",
    "Python": "backend/app",
    "Testing": "tests",
}

# Titles containing these read as open-ended → human-only.
_HUMAN_ONLY_MARKERS = ("design", "spike", "research", "investigate", "explore")


def _short(task_id: str) -> str:
    return hashlib.sha1(task_id.encode()).hexdigest()[:8]


class MockCodingAgent(CodingAgent):
    async def groom(self, task: dict) -> AgentSpec:
        tech = (task.get("technology") or "").strip()
        base = _TECH_DIR.get(tech, "backend/app")
        title = task.get("title") or "work item"
        return AgentSpec(
            task_id=str(task["id"]),
            summary=f"Implement: {title}",
            acceptance=[f"{title} behaves as described", "tests added/updated", "CI green"],
            target_dirs=[base],
            include_tests=settings.require_tests,
            notes=task.get("description") or None,
        )

    async def triage(self, task: dict, spec: AgentSpec) -> Suitability:
        title = (task.get("title") or "").lower()
        if any(marker in title for marker in _HUMAN_ONLY_MARKERS):
            return Suitability(
                suitable=False,
                reason="Open-ended / ambiguous work — better handled by a human.",
                confidence="high",
            )
        return Suitability(
            suitable=True,
            reason="Well-scoped, low-ambiguity, test coverage feasible.",
            confidence="medium",
        )

    async def run(
        self, spec: AgentSpec, branch: str, repo: str | None = None
    ) -> AgentRunResult:
        # ``repo`` doesn't affect the deterministic synthetic diff; accepted for
        # interface parity with the real adapter.
        return self._make_result(spec, branch)

    async def revise(
        self,
        spec: AgentSpec,
        prev: AgentRunResult,
        review_comment: str,
        repo: str | None = None,
    ) -> AgentRunResult:
        # Re-generate but keep the prior PR id/url so the PR is updated, not re-opened.
        result = self._make_result(spec, prev.branch_name)
        result.pr_id = prev.pr_id
        result.pr_url = prev.pr_url
        result.summary = f"Revised per review: {review_comment[:80]}"
        return result

    def _make_result(self, spec: AgentSpec, branch: str) -> AgentRunResult:
        sid = _short(spec.task_id)
        target = (spec.target_dirs or ["backend/app"])[0]
        impl_path = f"{target}/feature_{sid}.py"
        test_path = (
            f"{target}/test_feature_{sid}.py"
            if "test" in target
            else f"{target}/tests/test_feature_{sid}.py"
        )
        diff = (
            f"diff --git a/{impl_path} b/{impl_path}\n"
            "new file mode 100644\n--- /dev/null\n"
            f"+++ b/{impl_path}\n"
            "@@ -0,0 +1,3 @@\n"
            f"+def feature_{sid}():\n"
            f'+    """{spec.summary}"""\n'
            "+    return True\n"
            f"diff --git a/{test_path} b/{test_path}\n"
            "new file mode 100644\n--- /dev/null\n"
            f"+++ b/{test_path}\n"
            "@@ -0,0 +1,2 @@\n"
            f"+def test_feature_{sid}():\n"
            f"+    assert feature_{sid}() is True\n"
        )
        diff_lines = sum(
            1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
        )
        return AgentRunResult(
            branch_name=branch,
            diff=diff,
            diff_lines=diff_lines,
            pr_id=f"MOCK-PR-{sid}",
            pr_url=f"https://mock.local/pullrequest/{sid}",
            cost=1.0,
            summary=f"Implemented '{spec.summary}' on {branch}.",
            empty=False,
        )

    async def get_ci_status(
        self, pr_id: str, branch: str, poll_count: int = 0, repo: str | None = None
    ) -> CIStatus:
        # Deterministic: optionally fail the very first check (exercises the gate),
        # otherwise green. No clock/random — purely a function of poll_count/config.
        build = CIStatus(
            state="success",
            build_id=f"mock-build-{pr_id}",
            url=f"https://mock.local/build/{pr_id}",
        )
        if settings.mock_ci_fail_first and poll_count == 0:
            build.state = "failed"
        return build

    async def merge(self, pr_id: str, repo: str | None = None) -> MergeResult:
        return MergeResult(merged=True, commit_id=f"mocksha-{pr_id.lower()}")
