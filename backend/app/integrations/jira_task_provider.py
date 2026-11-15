"""Jira task provider (read side).

Maps the generic TaskProvider contract onto a Jira Cloud site (REST v3):

- external_id        -> issue key (e.g. "NW-42")
- sprint             -> fixVersions[0] (name = sprint name, path = "jira:<KEY>#<id>")
- board status       -> status.name checked against REVIEW_STATUSES first, then
                        statusCategory.key: new->backlog, indeterminate->in_progress,
                        done->done
- priority           -> priority.name (Highest/High->critical, Medium->medium,
                        Low/Lowest->low; anything else medium)
- work item type     -> issuetype.name as-is (Bug/Task/Story/...)
- description        -> Atlassian doc JSON flattened to plain text
- area/project       -> Jira has no area paths; project_name is the project key
                        (issue key prefix, e.g. "NW" from NW-42).

Writes (create/update) respect the same read_only dial as the other
providers: PUSH_ENABLED off means this provider refuses to mutate the site.
Status changes go through /issue/{key}/transitions (Jira has no direct
status edit); everything else is a PUT on the issue fields.
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal

import httpx

from app.integrations.task_provider import (
    ExternalSprint,
    ExternalTask,
    ExternalTaskCreate,
    ExternalTaskUpdate,
    ExternalTeamMember,
    RateLimitError,
    ReadOnlyProviderError,
    TaskPage,
    TaskProvider,
    TaskProviderTimeoutError,
)

logger = logging.getLogger(__name__)

# Board columns that mean "review" whatever their statusCategory says.
DEFAULT_REVIEW_STATUSES = ["In Review", "Review", "Code Review"]

_STATUS_CATEGORY: dict[str, Literal["backlog", "in_progress", "done"]] = {
    "new": "backlog",
    "indeterminate": "in_progress",
    "done": "done",
}
_PRIORITY_NAMES: dict[str, Literal["critical", "medium", "low"]] = {
    "Highest": "critical",
    "High": "critical",
    "Medium": "medium",
    "Low": "low",
    "Lowest": "low",
}
# Reverse of the read map. Jira's High reads back as "critical", so our "high"
# can't round-trip — 5 Jira priorities vs our 4, the read map is the truth.
_OUR_PRIORITY_TO_JIRA: dict[str, str] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}
# Board status -> Jira statusCategory.key to transition into.
_TARGET_CATEGORY: dict[str, str] = {
    "backlog": "new",
    "todo": "new",
    "in_progress": "indeterminate",
    "review": "indeterminate",
    "done": "done",
}


def _pick_transition(
    transitions: list[dict],
    target: str,
    review_statuses: list[str],
) -> dict | None:
    """Pick the transition that lands the issue in ``target``.

    "review" prefers a transition whose destination column is one of the
    configured review statuses (same names the read side trusts); every other
    target matches on destination statusCategory.
    """
    if target == "review":
        for t in transitions:
            if (t.get("to") or {}).get("name") in review_statuses:
                return t
    category = _TARGET_CATEGORY[target]
    for t in transitions:
        if ((t.get("to") or {}).get("statusCategory") or {}).get("key") == category:
            return t
    return None


def _text_doc(text: str | None) -> dict:
    """Plain text -> Atlassian Document Format (one paragraph per line)."""
    lines = (text or "").splitlines() or [""]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            for line in lines
        ],
    }


def _first(items: list | None) -> dict | None:
    return items[0] if items else None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _doc_text(doc: dict | None) -> str | None:
    """Flatten Atlassian Document Format (content[].content[].text) to text.

    ponytail: one text node per line; inline runs (bold within a paragraph)
    split too — the description is display-only prose, join properly if it
    ever feeds a diff or export.
    """
    if not isinstance(doc, dict):
        return None

    def walk(node) -> list[str]:
        if isinstance(node, dict):
            if "text" in node:
                return [node["text"]]
            return [t for c in node.get("content") or [] for t in walk(c)]
        if isinstance(node, list):
            return [t for c in node for t in walk(c)]
        return []

    return "\n".join(walk(doc.get("content"))) or None


class JiraTaskProvider(TaskProvider):
    """TaskProvider backed by Jira Cloud (REST v3, Basic email:api_token)."""

    def __init__(
        self,
        url: str,
        email: str,
        api_token: str,
        jql: str = "ORDER BY updated DESC",
        review_statuses: list[str] | None = None,
        read_only: bool = False,
        timeout: float = 20.0,
    ):
        if not url.startswith("http"):
            raise ValueError(
                f"jira provider needs url like https://x.atlassian.net, got {url!r}"
            )
        self.url = url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.jql = jql
        self.review_statuses = review_statuses or DEFAULT_REVIEW_STATUSES
        self.read_only = read_only
        self.timeout = timeout

    # -- plumbing ---------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.url,
            auth=(self.email, self.api_token),
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )

    def _check_writable(self) -> None:
        if self.read_only:
            raise ReadOnlyProviderError(
                "Jira provider is read-only (PUSH_ENABLED off); "
                f"refusing to create/update issues on {self.url}"
            )

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        # ponytail: one retry with backoff on 5xx; a real retry queue belongs
        # to the sync job, not the provider.
        for attempt in range(2):
            try:
                async with self._client() as client:
                    resp = await client.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                raise TaskProviderTimeoutError(str(exc)) from exc
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After") or "60"
                try:
                    wait = max(1, int(retry_after))
                except ValueError:
                    wait = 60
                raise RateLimitError("Jira rate limit exceeded", retry_after=wait)
            if resp.status_code < 500 or attempt == 1:
                return resp
            await asyncio.sleep(1.5)
        raise AssertionError("unreachable: loop returns on attempt 2")

    # -- mapping ----------------------------------------------------------

    def _map_status(self, fields: dict) -> Literal["backlog", "todo", "in_progress", "review", "done"]:
        status = fields.get("status") or {}
        if status.get("name") in self.review_statuses:
            return "review"
        category = ((status.get("statusCategory") or {}).get("key")) or "new"
        return _STATUS_CATEGORY.get(category, "backlog")

    def _map_issue(self, issue: dict) -> ExternalTask:
        fields = issue.get("fields") or {}
        key = issue["key"]
        fix_version = _first(fields.get("fixVersions"))

        return ExternalTask(
            external_id=key,
            title=fields.get("summary", ""),
            area_path=None,
            project_name=key.split("-", 1)[0],
            iteration_path=(
                f"jira:{key.split('-', 1)[0]}#{fix_version['id']}"
                if fix_version and fix_version.get("id")
                else None
            ),
            sprint_name=(fix_version["name"] if fix_version else None),
            work_item_type=(fields.get("issuetype") or {}).get("name") or "Issue",
            description=_doc_text(fields.get("description")),
            acceptance_criteria=None,  # no separate field; AC live in the description
            status=self._map_status(fields),
            priority=_PRIORITY_NAMES.get(
                (fields.get("priority") or {}).get("name", ""), "medium"
            ),
            assignee_name=((fields.get("assignee") or {}).get("displayName")),
            assignee_external_id=str((fields.get("assignee") or {}).get("accountId"))
            if fields.get("assignee")
            else None,
            story_points=None,  # customfield id varies per site; leave unset
            estimated_hours=None,  # Jira has no native hours field
            external_state=(fields.get("status") or {}).get("name"),
            state_changed_at=None,  # changelog isn't in the search payload
            external_changed_at=_parse_iso(fields.get("updated")),
            tags=",".join(fields.get("labels") or []) or None,
        )

    # -- read side --------------------------------------------------------

    async def _search(self, params: dict) -> httpx.Response:
        """Search; falls back to the POST endpoint on newer Jira Cloud sites
        that have removed the deprecated GET /rest/api/3/search (410)."""
        resp = await self._request("GET", "/rest/api/3/search", params=params)
        if resp.status_code == 410:
            resp = await self._request("POST", "/rest/api/3/search/jql", json=params)
        return resp

    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        start_at = (page - 1) * page_size
        resp = await self._search(
            {"jql": self.jql, "startAt": start_at, "maxResults": page_size}
        )
        if resp.status_code == 400:
            # Jira answers a bad JQL with 400 + an errors object in the body.
            raise ValueError(f"Jira rejected JQL {self.jql!r}: {resp.text}")
        resp.raise_for_status()
        body = resp.json()
        issues = body.get("issues", [])
        # POST /search/jql has no "total"; per-page truth like the GitHub
        # provider, and "isLast" when the site provides it.
        total = body.get("total", start_at + len(issues))
        if "isLast" in body:
            has_more = not body["isLast"]
        else:
            has_more = start_at + len(issues) < total
        return TaskPage(
            items=[self._map_issue(i) for i in issues],
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    async def get_task(self, external_id: str) -> ExternalTask | None:
        resp = await self._request("GET", f"/rest/api/3/issue/{external_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._map_issue(resp.json())

    async def sync_tasks(self) -> list[ExternalTask]:
        out: list[ExternalTask] = []
        page = 1
        while True:
            task_page = await self.list_tasks(page=page, page_size=50)
            out.extend(task_page.items)
            if not task_page.has_more:
                return out
            page += 1

    async def _project_key(self) -> str | None:
        """Project the configured JQL points at (key prefix of its first issue)."""
        resp = await self._search(
            {"jql": self.jql, "maxResults": 1, "fields": "key"}
        )
        if resp.status_code != 200:
            logger.warning("could not resolve Jira project key; sprints will be empty")
            return None
        issues = resp.json().get("issues") or []
        return issues[0]["key"].split("-", 1)[0] if issues else None

    async def list_sprints(self) -> list[ExternalSprint]:
        key = await self._project_key()
        if key is None:
            return []
        resp = await self._request("GET", f"/rest/api/3/project/{key}/versions")
        resp.raise_for_status()
        sprints: list[ExternalSprint] = []
        for v in resp.json():
            released = _parse_iso(v.get("releaseDate"))
            sprints.append(
                ExternalSprint(
                    name=v["name"],
                    path=f"jira:{key}#{v['id']}",
                    start_date=None,
                    end_date=(released.date() if released else None),
                )
            )
        return sprints

    async def list_team_members(self) -> list[ExternalTeamMember]:
        # Needs a real site's permissions to be useful; the import falls back
        # to matching issue assignees by display name.
        return []

    # -- write side -------------------------------------------------------

    async def _assignee_id(self, name: str) -> str:
        """Jira Cloud assigns by accountId, not display name; look it up."""
        resp = await self._request(
            "GET", "/rest/api/3/users/search", params={"query": name}
        )
        resp.raise_for_status()
        for user in resp.json():
            if user.get("active", True) and user.get("accountId") and \
                    user.get("displayName", "").lower() == name.lower():
                return user["accountId"]
        raise ValueError(f"no active Jira user matching {name!r}")

    async def _transition(self, external_id: str, target: str) -> None:
        """Move an issue to ``target`` via the board's available transitions."""
        resp = await self._request("GET", f"/rest/api/3/issue/{external_id}/transitions")
        resp.raise_for_status()
        transitions = resp.json().get("transitions", [])
        pick = _pick_transition(transitions, target, self.review_statuses)
        if pick is None:
            raise ValueError(
                f"no transition to {target!r} available on {external_id} "
                f"(has: {[t.get('name') for t in transitions]})"
            )
        resp = await self._request(
            "POST", f"/rest/api/3/issue/{external_id}/transitions", json={"id": pick["id"]}
        )
        resp.raise_for_status()

    async def create_task(self, task: ExternalTaskCreate) -> ExternalTask:
        self._check_writable()
        project_key = await self._project_key()
        if project_key is None:
            raise ValueError(
                f"could not resolve a Jira project from JQL {self.jql!r}; "
                "point JIRA_JQL at one project (e.g. \"project = NW\")"
            )
        body = task.description or ""
        if task.acceptance_criteria:
            body += f"\n\n## Acceptance criteria\n{task.acceptance_criteria}"
        fields: dict = {
            "project": {"key": project_key},
            "summary": task.title,
            "issuetype": {"name": "Task"},
            "description": _text_doc(body or None),
            "priority": {"name": _OUR_PRIORITY_TO_JIRA[task.priority]},
        }
        if task.assignee_name:
            fields["assignee"] = {"id": await self._assignee_id(task.assignee_name)}
        resp = await self._request("POST", "/rest/api/3/issue", json={"fields": fields})
        if resp.status_code == 400:
            raise ValueError(f"Jira rejected create: {resp.text}")
        resp.raise_for_status()
        created = await self.get_task(resp.json()["key"])
        if created is None:  # deleted between create and read — should not happen
            raise ValueError(f"issue {resp.json()['key']} vanished right after create")
        # New issues land in the board's first column; move if asked further.
        if task.status not in ("backlog", "todo") and created.status != task.status:
            await self._transition(created.external_id, task.status)
            created = await self.get_task(created.external_id)
            assert created is not None
        return created

    async def update_task(
        self, external_id: str, changes: ExternalTaskUpdate
    ) -> ExternalTask:
        self._check_writable()
        current = await self.get_task(external_id)
        if current is None:
            raise ValueError(f"issue {external_id} not found in {self.url}")

        fields: dict = {}
        if changes.title is not None:
            fields["summary"] = changes.title
        if changes.description is not None:
            fields["description"] = _text_doc(changes.description)
        if changes.priority is not None:
            fields["priority"] = {"name": _OUR_PRIORITY_TO_JIRA[changes.priority]}
        if changes.assignee_name is not None:
            fields["assignee"] = {"id": await self._assignee_id(changes.assignee_name)}
        if fields:
            resp = await self._request(
                "PUT", f"/rest/api/3/issue/{external_id}", json={"fields": fields}
            )
            resp.raise_for_status()
        # PUT returns 204 with no body, so the final state is re-read below.
        if changes.status is not None and changes.status != current.status:
            await self._transition(external_id, changes.status)
        final = await self.get_task(external_id)
        assert final is not None  # it existed a moment ago; a delete race is fine to crash on
        return final
