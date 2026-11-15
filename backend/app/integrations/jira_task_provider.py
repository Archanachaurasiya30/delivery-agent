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

Writes (create/update) are not implemented yet — see issue #4. The factory
still wires read_only=not PUSH_ENABLED so the dial is honored the day they are.
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

    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        start_at = (page - 1) * page_size
        resp = await self._request(
            "GET",
            "/rest/api/3/search",
            params={"jql": self.jql, "startAt": start_at, "maxResults": page_size},
        )
        if resp.status_code == 400:
            # Jira answers a bad JQL with 400 + an errors object in the body.
            raise ValueError(f"Jira rejected JQL {self.jql!r}: {resp.text}")
        resp.raise_for_status()
        body = resp.json()
        issues = body.get("issues", [])
        total = body.get("total", len(issues))
        return TaskPage(
            items=[self._map_issue(i) for i in issues],
            total=total,
            page=page,
            page_size=page_size,
            has_more=start_at + len(issues) < total,
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
        resp = await self._request(
            "GET",
            "/rest/api/3/search",
            params={"jql": self.jql, "maxResults": 1, "fields": "key"},
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

    async def create_task(self, task: ExternalTaskCreate) -> ExternalTask:
        raise NotImplementedError("Jira write side not implemented yet — see issue #4")

    async def update_task(
        self, external_id: str, changes: ExternalTaskUpdate
    ) -> ExternalTask:
        raise NotImplementedError("Jira write side not implemented yet — see issue #4")
