"""Real CodingAgent backed by the headless Claude Code CLI.

Each run gets a throwaway git workspace under ``workspace_root``: the
ORCHESTRATOR owns every git operation (clone, branch, commit, push) while
Claude Code only edits the working tree — it is explicitly forbidden from
running git. The PAT never touches argv, the remote URL, or ``.git/config``:
it rides as an ``http.extraHeader`` via ``GIT_CONFIG_*`` env vars on each git
subprocess, and those vars are stripped from the Claude subprocess env.

Flow per ``run``:
  1. Clone the default branch into ``{workspace_root}/{task_id}``, branch off.
  2. Run ``claude -p`` with ``--output-format stream-json``, mapping stream
     events to run-event emits (lifecycle / assistant / file_edit / command /
     inspect / error / result) through ``self.event_sink``.
  3. Stage everything, capture the cached diff, and enforce the SAME diff
     guardrails as ``CodingRunService`` BEFORE anything is pushed.
  4. Commit + push the agent branch, then open a PR via ``AdoGitClient``
     (falling back to the already-open PR on retries).

Lazily imported by the factory so non-claude deployments never need the CLI
or the OAuth token.
"""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.integrations.ado_git_client import AdoGitClient
from app.integrations.coding_agent import (
    AgentRunResult,
    AgentSpec,
    CIStatus,
    CodingAgent,
    CodingAgentError,
    GuardrailViolation,
    MergeResult,
    NoRepoConfiguredError,
    Suitability,
)
from app.services.run_event_service import EventSink

logger = logging.getLogger(__name__)

# stream-json tool-result lines can be huge (whole-file reads) — default 64KiB
# StreamReader limit would kill the session mid-run.
_STREAM_LIMIT = 10 * 1024 * 1024
_STDERR_TAIL = 2000

# Claude may read/edit/write and run the test toolchain — but never git, never
# the network. Version control stays with the orchestrator.
_ALLOWED_TOOLS = (
    "Read,Glob,Grep,LS,Write,Edit,MultiEdit,"
    "Bash(python:*),Bash(python3:*),Bash(pytest:*),Bash(pip:*),"
    "Bash(ls:*),Bash(cat:*),Bash(mkdir:*)"
)
_DISALLOWED_TOOLS = "Bash(git:*),WebFetch,WebSearch"


@dataclass
class _ClaudeOutcome:
    """What a finished Claude Code session boils down to."""

    summary: str
    cost: float
    num_turns: int


@dataclass
class _StreamState:
    """Mutable accumulator while consuming the stream-json output."""

    last_assistant_text: str = ""
    result_subtype: str | None = None
    result_text: str = ""
    cost: float = 0.0
    num_turns: int = 0
    stderr_tail: str = ""


class ClaudeCodeCodingAgent(CodingAgent):
    def __init__(
        self,
        org_url: str,
        project: str,
        default_repo: str,
        pat: str,
        default_branch: str = "main",
        pipeline_id: str = "",
        model: str = "",
        max_turns: int = 50,
        timeout_seconds: int = 1500,
        workspace_root: str = "/workspaces",
    ) -> None:
        # Config-only: this is also constructed in the API process, so no
        # CLI/token checks here — those happen at run() time (preflight).
        # default_repo MAY be empty: dispatch passes a per-run repo.
        if not (org_url and project):
            raise NoRepoConfiguredError(
                "Claude Code coding agent needs tfs_url + azure_repo_project (or tfs_project)."
            )
        self.default_repo = default_repo
        self.default_branch = default_branch
        self.pipeline_id = pipeline_id
        self.model = model
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.workspace_root = workspace_root
        self.ado = AdoGitClient(org_url, project, pat)
        # Set per-run by CodingRunService (RunEventRecorder.emit); guarded no-op
        # when unset so the adapter also works without event wiring.
        self.event_sink: EventSink | None = None
        # Kept ONLY to build the per-command git auth header.
        self._pat = pat

    # ---- event plumbing --------------------------------------------------
    async def _emit(self, kind: str, message: str, payload: dict | None = None) -> None:
        if self.event_sink is None:
            return
        await self.event_sink(kind, message, payload)

    # ---- grooming / triage (shared spec LLM) ------------------------------
    async def groom(self, task: dict) -> AgentSpec:
        # Lazy import so constructing the adapter never needs an LLM key.
        from app.integrations import spec_llm

        return await spec_llm.groom_task(task)

    async def triage(self, task: dict, spec: AgentSpec) -> Suitability:
        from app.integrations import spec_llm

        return await spec_llm.triage_spec(task, spec)

    # ---- git plumbing ------------------------------------------------------
    def _git_env(self) -> dict[str, str]:
        """Env for git subprocesses: PAT as an extraHeader, never on disk/argv."""
        token = base64.b64encode(f":{self._pat}".encode()).decode()
        env = dict(os.environ)
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {token}",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        return env

    async def _git(self, workspace: Path, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(workspace),
            env=self._git_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise CodingAgentError(
                f"git {' '.join(args[:3])} failed: {stderr.decode(errors='replace')[-500:]}"
            )
        return stdout.decode(errors="replace")

    async def _prepare_workspace(
        self, workspace: Path, clone_url: str, repo_name: str, base_branch: str
    ) -> None:
        shutil.rmtree(workspace, ignore_errors=True)  # leftover from a prior attempt
        workspace.parent.mkdir(parents=True, exist_ok=True)
        await self._emit("lifecycle", f"Cloning {repo_name}")
        await self._git(
            workspace.parent,
            "clone", "--branch", base_branch, "--single-branch", clone_url, str(workspace),
        )

    async def _stage_and_diff(self, workspace: Path) -> tuple[str, int, list[str]]:
        await self._git(workspace, "add", "-A")
        diff = await self._git(workspace, "diff", "--cached")
        # Paths come from --name-only -z, NOT from parsing "+++ b/" headers:
        # header parsing misses deletions (+++ /dev/null), pure renames, and
        # binary files, and -z sidesteps core.quotePath mangling.
        raw = await self._git(workspace, "diff", "--cached", "--name-only", "-z")
        paths = [p for p in raw.split("\0") if p]
        return diff, self._count_diff_lines(diff), paths

    async def _commit(self, workspace: Path, message: str) -> None:
        await self._git(
            workspace,
            "-c", "user.name=Delivery Coding Agent",
            "-c", "user.email=agent@delivery.local",
            "commit", "-m", message,
        )

    @staticmethod
    def _count_diff_lines(diff: str) -> int:
        """Changed lines (+/-) excluding the +++/--- file headers."""
        return sum(
            1
            for ln in diff.splitlines()
            if (ln.startswith("+") or ln.startswith("-"))
            and not ln.startswith(("+++", "---"))
        )

    # ---- guardrails (pre-push) ---------------------------------------------
    @staticmethod
    def _enforce_pre_push_guardrails(diff_lines: int, paths: list[str]) -> None:
        """Same rules as CodingRunService._enforce_diff_guardrails — but BEFORE
        anything leaves the workspace, so a breaching diff is never pushed.
        ``paths`` comes from git --name-only so deletions/renames/binary files
        are covered too."""
        if diff_lines > settings.coding_agent_max_diff_lines:
            raise GuardrailViolation(
                f"Diff too large: {diff_lines} > {settings.coding_agent_max_diff_lines} lines."
            )
        allowed = [d.strip() for d in settings.coding_agent_allowed_dirs.split(",") if d.strip()]
        if allowed:
            bad = [p for p in paths if not any(p.startswith(a) for a in allowed)]
            if bad:
                raise GuardrailViolation(f"Diff touches disallowed paths: {bad}")
        if settings.require_tests and not any("test" in p.lower() for p in paths):
            raise GuardrailViolation("require_tests is on but the diff touches no test files.")

    # ---- repo resolution ------------------------------------------------------
    def _resolve_repo(self, repo: str | None) -> tuple[str, str]:
        """Normalize a per-dispatch repo (bare name or URL) to
        ``(repo_name, clone_url)``.

        A URL is only accepted when it lives under the configured ADO org —
        the PAT rides on every git call as an extraHeader, so cloning an
        arbitrary host would hand it the credential. The bare name is what
        every AdoGitClient REST call needs (PR create/find, merge)."""
        value = repo or self.default_repo
        if not value:
            raise NoRepoConfiguredError("No target repository configured for this run.")
        if value.startswith("http"):
            base = self.ado.org_url
            if value != base and not value.startswith(base + "/"):
                raise CodingAgentError(
                    f"Refusing to use a repository outside the configured ADO org: {value}"
                )
            name = value.rstrip("/").rsplit("/", 1)[-1]
            if not name or "_git" in name:
                raise CodingAgentError(f"Cannot derive a repository name from: {value}")
            return name, value
        if not re.fullmatch(r"[A-Za-z0-9._ -]+", value):
            raise CodingAgentError(f"Invalid repository name: {value!r}")
        return value, self.ado.clone_url(value)

    # ---- preflight -----------------------------------------------------------
    @staticmethod
    def _preflight() -> str:
        """Fail fast (before any clone) if the worker can't actually run Claude."""
        if shutil.which("claude") is None:
            raise CodingAgentError("Claude Code CLI not found in worker image")
        token = settings.claude_code_oauth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        if not token:
            raise CodingAgentError("CLAUDE_CODE_OAUTH_TOKEN not configured")
        return token

    # ---- prompt ---------------------------------------------------------------
    def _build_prompt(self, spec: AgentSpec, review_comment: str | None = None) -> str:
        acceptance = "\n".join(f"- {a}" for a in spec.acceptance) or "- Implements the work item"
        lines = [
            "You are implementing a work item in the repository at the current directory.",
            "",
            "## Task",
            spec.summary,
            "",
            "## Acceptance criteria",
            acceptance,
            "",
            "## Additional context",
            spec.notes or "(none)",
        ]
        if review_comment:
            lines += [
                "",
                "## Review feedback to address",
                "A reviewer looked at your previous attempt on this branch:",
                review_comment,
            ]
        lines += [
            "",
            "## Rules",
            "- First explore the repository structure, then implement the change.",
        ]
        if spec.target_dirs:
            lines.append(f"- Only modify files under: {', '.join(spec.target_dirs)}.")
        lines.append(
            f"- Keep the total change under {settings.coding_agent_max_diff_lines} changed lines."
        )
        if spec.include_tests:
            lines.append(
                "- Add or update tests covering the change (test files live under tests/). "
                "Run the test suite (pytest) to verify before finishing."
            )
        lines.append(
            "- Do NOT run any git commands and do NOT create commits — "
            "the orchestrator handles version control."
        )
        lines.append("- When done, summarize what you changed in one short paragraph.")
        return "\n".join(lines)

    # ---- Claude subprocess -------------------------------------------------
    async def _run_claude(self, prompt: str, workspace: Path) -> _ClaudeOutcome:
        token = self._preflight()
        argv = [
            "claude", "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", "acceptEdits",
            "--allowed-tools", _ALLOWED_TOOLS,
            "--disallowed-tools", _DISALLOWED_TOOLS,
            "--max-turns", str(self.max_turns),
        ]
        if self.model:
            argv += ["--model", self.model]
        # Build the child env from a minimal ALLOWLIST, never os.environ: the
        # prompt embeds untrusted work-item text and Claude can run python/pip,
        # so a denylist would leak every other worker secret (DATABASE_URL,
        # REDIS_URL, GROQ_API_KEY, TELEGRAM_BOT_TOKEN, the PAT, ...) into a
        # code-executing, network-capable subprocess. The OAuth token is the
        # only credential Claude gets.
        env = {
            k: os.environ[k]
            for k in ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "USER", "SHELL")
            if k in os.environ
        }
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workspace),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_STREAM_LIMIT,
        )
        state = _StreamState()
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self._consume_stdout(proc.stdout, state, workspace),
                    self._consume_stderr(proc.stderr, state),
                ),
                timeout=self.timeout_seconds,
            )
        except BaseException as exc:
            # Never leave the claude process running: kill on timeout,
            # cancellation, or any stream-handling error — an orphan keeps
            # burning billed turns while the finally-block rmtrees its cwd.
            # (No unconditional finally-kill: on the normal path streams EOF
            # just before exit and killing there would corrupt the exit code.)
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.wait()
            if isinstance(exc, asyncio.TimeoutError):
                raise CodingAgentError(
                    f"Claude Code timed out after {self.timeout_seconds}s"
                ) from exc
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise CodingAgentError(f"Claude Code stream processing failed: {exc}") from exc
        returncode = await proc.wait()

        if returncode != 0 or state.result_subtype != "success":
            detail = state.result_text or state.last_assistant_text or state.stderr_tail
            raise CodingAgentError(
                f"Claude Code failed (exit {returncode}, "
                f"result {state.result_subtype or 'missing'}): {detail[:500]}"
            )
        summary = (state.result_text or state.last_assistant_text).strip()[:500]
        return _ClaudeOutcome(
            summary=summary or "Claude Code session completed.",
            cost=state.cost,
            num_turns=state.num_turns,
        )

    async def _consume_stdout(
        self, stream: asyncio.StreamReader, state: _StreamState, workspace: Path
    ) -> None:
        while True:
            try:
                line = await stream.readline()
            except ValueError:
                # A single stream-json line over _STREAM_LIMIT (huge tool
                # result). readline() already discarded the buffered data, so
                # skip it rather than failing an otherwise-healthy session.
                logger.warning("Skipping Claude stream line over %d bytes", _STREAM_LIMIT)
                continue
            if not line:
                break
            raw = line.decode(errors="replace").strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                logger.debug("Unparseable Claude stream line: %s", raw[:200])
                continue
            await self._handle_event(event, state, workspace)

    @staticmethod
    async def _consume_stderr(stream: asyncio.StreamReader, state: _StreamState) -> None:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            state.stderr_tail = (state.stderr_tail + chunk.decode(errors="replace"))[-_STDERR_TAIL:]

    async def _handle_event(self, event: dict, state: _StreamState, workspace: Path) -> None:
        etype = event.get("type")
        if etype == "system" and event.get("subtype") == "init":
            model = event.get("model") or self.model or "default"
            await self._emit(
                "lifecycle",
                f"Claude Code session started (model {model})",
                {"tools": (event.get("tools") or [])[:30]},
            )
        elif etype == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text") or ""
                    if text.strip():
                        state.last_assistant_text = text
                        await self._emit("assistant", text[:300], {"text": text[:2000]})
                elif block.get("type") == "tool_use":
                    await self._emit_tool_use(block, workspace)
        elif etype == "user":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and block.get("is_error")
                ):
                    text = self._tool_result_text(block)
                    await self._emit("error", f"Tool call failed: {text[:300]}", {})
        elif etype == "result":
            state.result_subtype = event.get("subtype") or ""
            state.cost = float(event.get("total_cost_usd") or 0.0)
            state.num_turns = int(event.get("num_turns") or 0)
            state.result_text = str(event.get("result") or "")
            await self._emit(
                "result",
                f"Session finished: {state.num_turns} turns",
                {
                    "subtype": state.result_subtype,
                    "total_cost_usd": state.cost,
                    "duration_ms": event.get("duration_ms"),
                },
            )

    async def _emit_tool_use(self, block: dict, workspace: Path) -> None:
        name = block.get("name") or ""
        tool_input = block.get("input") or {}
        if name in ("Edit", "Write", "MultiEdit"):
            file_path = str(tool_input.get("file_path") or "")
            verb = "Writing" if name == "Write" else "Editing"
            await self._emit(
                "file_edit",
                f"{verb} {self._relative(file_path, workspace)}",
                {"tool": name, "file_path": file_path},
            )
        elif name == "Bash":
            command = str(tool_input.get("command") or "")
            await self._emit(
                "command",
                f"Running: {command[:200]}",
                {"command": command, "description": tool_input.get("description")},
            )
        elif name in ("Read", "Glob", "Grep", "LS"):
            await self._emit("inspect", self._inspect_line(name, tool_input, workspace), tool_input)

    @staticmethod
    def _relative(file_path: str, workspace: Path) -> str:
        try:
            return str(Path(file_path).relative_to(workspace))
        except ValueError:
            return file_path

    def _inspect_line(self, name: str, tool_input: dict, workspace: Path) -> str:
        if name == "Read":
            return f"Reading {self._relative(str(tool_input.get('file_path') or ''), workspace)}"
        if name in ("Glob", "Grep"):
            return f"Searching for {str(tool_input.get('pattern') or '')[:200]}"
        return f"Listing {self._relative(str(tool_input.get('path') or ''), workspace)}"

    @staticmethod
    def _tool_result_text(block: dict) -> str:
        content = block.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                str(c.get("text") or "") for c in content if isinstance(c, dict)
            )
        return ""

    # ---- PR plumbing -----------------------------------------------------------
    async def _open_pr(
        self, repo_name: str, branch: str, spec: AgentSpec, summary: str
    ) -> tuple[str, str]:
        description = "\n".join(
            [summary, "", "Acceptance criteria:"]
            + [f"- {a}" for a in (spec.acceptance or ["Implements the work item"])]
            + ["", "Opened by the delivery coding agent (Claude Code). Review before merge."]
        )
        try:
            return await self.ado.create_pr(
                repo_name, branch, self.default_branch,
                title=spec.summary[:200], description=description,
            )
        except Exception:  # noqa: BLE001 - retry case: the PR may already be open
            existing = await self.ado.find_active_pr(repo_name, branch)
            if existing is None:
                raise
            return existing

    # ---- CodingAgent interface --------------------------------------------------
    async def run(self, spec: AgentSpec, branch: str, repo: str | None = None) -> AgentRunResult:
        repo_name, clone_url = self._resolve_repo(repo)
        self._preflight()
        workspace = Path(self.workspace_root) / spec.task_id
        try:
            await self._prepare_workspace(workspace, clone_url, repo_name, self.default_branch)
            await self._git(workspace, "checkout", "-b", branch)
            await self._emit("lifecycle", f"Created branch {branch}")
            await self._emit("lifecycle", "Claude Code session starting")
            outcome = await self._run_claude(self._build_prompt(spec), workspace)
            diff, diff_lines, paths = await self._stage_and_diff(workspace)
            if not paths:
                # Nothing pushed; the service raises GuardrailViolation on empty.
                return AgentRunResult(
                    branch_name=branch, empty=True,
                    summary="Agent produced no changes.", cost=outcome.cost,
                )
            self._enforce_pre_push_guardrails(diff_lines, paths)
            await self._commit(workspace, (outcome.summary or spec.summary).splitlines()[0])
            # Force: the agent owns this branch, and a retry after a partial
            # prior attempt must not fail on a non-fast-forward.
            await self._git(workspace, "push", "--force", "origin", branch)
            await self._emit("lifecycle", "Pushed branch")
            pr_id, pr_url = await self._open_pr(repo_name, branch, spec, outcome.summary)
            await self._emit("lifecycle", f"Pull request #{pr_id} opened", {"pr_url": pr_url})
            return AgentRunResult(
                branch_name=branch, diff=diff, diff_lines=diff_lines,
                pr_id=pr_id, pr_url=pr_url, cost=outcome.cost, summary=outcome.summary,
            )
        finally:
            if not settings.claude_code_keep_workspace:
                shutil.rmtree(workspace, ignore_errors=True)

    async def revise(
        self,
        spec: AgentSpec,
        prev: AgentRunResult,
        review_comment: str,
        repo: str | None = None,
    ) -> AgentRunResult:
        repo_name, clone_url = self._resolve_repo(repo)
        self._preflight()
        branch = prev.branch_name
        workspace = Path(self.workspace_root) / spec.task_id
        try:
            # The remote branch is the source of truth for the previous attempt.
            await self._prepare_workspace(workspace, clone_url, repo_name, branch)
            await self._emit("lifecycle", "Claude Code session starting")
            outcome = await self._run_claude(
                self._build_prompt(spec, review_comment=review_comment), workspace
            )
            # Diff is relative to the branch tip — the revision delta only.
            diff, diff_lines, paths = await self._stage_and_diff(workspace)
            if not paths:
                return AgentRunResult(
                    branch_name=branch, pr_id=prev.pr_id, pr_url=prev.pr_url,
                    empty=True, cost=outcome.cost,
                )
            self._enforce_pre_push_guardrails(diff_lines, paths)
            await self._commit(workspace, (outcome.summary or spec.summary).splitlines()[0])
            # Plain push — appending to the branch keeps the PR's history intact.
            await self._git(workspace, "push", "origin", branch)
            await self._emit("lifecycle", "Pushed branch")
            return AgentRunResult(
                branch_name=branch, diff=diff, diff_lines=diff_lines,
                pr_id=prev.pr_id, pr_url=prev.pr_url, cost=outcome.cost,
                summary=f"Revised: {outcome.summary}",
            )
        finally:
            if not settings.claude_code_keep_workspace:
                shutil.rmtree(workspace, ignore_errors=True)

    async def get_ci_status(
        self, pr_id: str, branch: str, poll_count: int = 0, repo: str | None = None
    ) -> CIStatus:
        if not self.pipeline_id:
            # No pipeline configured → nothing to gate on; treat as success.
            return CIStatus(state="success")
        build = await self.ado.get_latest_build(self.pipeline_id, branch)
        if build is None:
            return CIStatus(state="not_found")
        build_id = str(build.get("id"))
        url = build.get("_links", {}).get("web", {}).get("href")
        if build.get("status") != "completed":
            return CIStatus(state="running", build_id=build_id, url=url)
        state = "success" if build.get("result") == "succeeded" else "failed"
        return CIStatus(state=state, build_id=build_id, url=url)

    async def merge(self, pr_id: str, repo: str | None = None) -> MergeResult:
        repo_name, _ = self._resolve_repo(repo)
        pr = await self.ado.complete_pr(repo_name, pr_id)
        return MergeResult(
            merged=pr.get("status") == "completed",
            commit_id=(pr.get("lastMergeCommit") or {}).get("commitId"),
        )
