"""Azure DevOps / TFS TaskProvider implementation.

Conforms to the TaskProvider abstraction against the Azure DevOps REST API
(api-version 7.1). Auth is a Personal Access Token sent as HTTP Basic
``base64(":" + pat)``.

Field/state/priority maps assume the **Agile** process template defaults and
are module-level dicts so they can be tuned if your project uses Scrum/CMMI.
"""

import base64
import html
import logging
import re
from datetime import date, datetime

import httpx

from app.integrations.task_provider import (
    ExternalSprint,
    ExternalTask,
    ExternalTaskCreate,
    ExternalTaskUpdate,
    RateLimitError,
    ReadOnlyProviderError,
    TaskPage,
    TaskProvider,
    TaskProviderTimeoutError,
)

# Cloud (dev.azure.com) speaks 7.1. On-prem Azure DevOps Server pins to the
# release: 2022 -> 7.1, 2020 -> 6.0, 2019 -> 5.0. Override with TFS_API_VERSION
# when pointing at an on-prem collection.
API_VERSION = "7.1"

# Our status  ->  ADO System.State.
# Scrum-oriented (the Northwind instance runs Scrum). WRITE-ONLY, and unused
# while PUSH_ENABLED=false — verify against the target type before enabling push.
STATUS_TO_STATE = {
    "backlog": "New",
    "todo": "Approved",
    "in_progress": "Committed",
    "review": "Committed",
    "done": "Done",
}

# ADO System.State -> our status.
#
# Keyed by lowercased state name (see _map_state) so casing differences between
# work item types don't cause silent misses. Covers the Agile, Scrum and CMMI
# defaults plus the custom states on the Northwind instance; unknown states
# fall back to "backlog" and are logged once so they can be added here.
STATE_TO_STATUS = {
    # --- Proposed / not started ---
    "new": "backlog",
    "proposed": "backlog",
    "to be discussed": "backlog",
    "in planning": "backlog",
    "scope": "backlog",
    "business": "backlog",
    "innovation": "backlog",
    "inactive": "backlog",
    "requested": "backlog",
    # --- Ready to be picked up ---
    "to do": "todo",
    "approved": "todo",
    "ready": "todo",
    "scheduled": "todo",
    "discussed": "todo",
    "open": "todo",
    # --- Underway ---
    "active": "in_progress",
    "committed": "in_progress",       # Scrum: committed to the sprint
    "in progress": "in_progress",
    "under analysis": "in_progress",
    "arch": "in_progress",
    "design": "in_progress",
    "development": "in_progress",
    "on hold": "in_progress",         # started, then blocked
    "failed": "in_progress",          # bounced back for rework
    # --- Done building, awaiting verification/release ---
    "resolved": "review",
    "pre-read ready": "review",
    "ready for production": "review",
    "waiting for deployment": "review",
    # --- Terminal ---
    "done": "done",
    "closed": "done",
    "completed": "done",
    "accepted": "done",
    "rejected": "done",
    "not a bug": "done",
    "removed": "done",
}

# Work item types worth mirroring onto the board. The others this server
# defines — Code Review Request/Response, Feedback Request/Response, Shared
# Steps, Shared Parameter — are tooling artifacts, not delivery work, and they
# dominate the raw work-item count.
DEFAULT_SYNC_TYPES = (
    "Product Backlog Item", "Task", "Bug", "Feature", "Epic", "Impediment",
    "Issue", "Release",
    "User Story", "Requirement",  # Agile/CMMI equivalents
)

# States meaning "this work item was deleted/abandoned". Counting them as done
# would inflate completion and corrupt velocity, so they are filtered out of
# the sync entirely rather than mapped to a status.
EXCLUDED_STATES = ("Removed",)

# Our priority  ->  ADO Microsoft.VSTS.Common.Priority (1 highest .. 4 lowest)
PRIORITY_TO_ADO = {"critical": 1, "high": 2, "medium": 3, "low": 4}
ADO_TO_PRIORITY = {1: "critical", 2: "high", 3: "medium", 4: "low"}

# ADO field names
F_TITLE = "System.Title"
F_DESCRIPTION = "System.Description"
F_STATE = "System.State"
F_PRIORITY = "Microsoft.VSTS.Common.Priority"
F_ASSIGNED = "System.AssignedTo"
F_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
F_EFFORT = "Microsoft.VSTS.Scheduling.Effort"            # Scrum PBI equivalent
F_ESTIMATE = "Microsoft.VSTS.Scheduling.OriginalEstimate"  # hours, on Tasks
F_ACCEPTANCE = "Microsoft.VSTS.Common.AcceptanceCriteria"
# Bugs and Issues carry their detail in ReproSteps, not Description.
F_REPRO = "Microsoft.VSTS.TCM.ReproSteps"
F_TYPE = "System.WorkItemType"
# Area = stream/project grouping, Iteration = sprint. Independent axes in ADO.
F_AREA = "System.AreaPath"
F_ITERATION = "System.IterationPath"
# Blocker-detection signals: when the state last changed (staleness), when
# anything changed (data freshness), tags ("Blocked"), and this instance's
# custom "Why On Hold" field. WhyOnHold is read from dumps only — asking the
# live batch API for a field a server doesn't define fails the whole request.
F_STATE_CHANGED = "Microsoft.VSTS.Common.StateChangeDate"
F_CHANGED = "System.ChangedDate"
F_TAGS = "System.Tags"
F_WHY_ON_HOLD = "Custom.WhyOnHold"
FETCH_FIELDS = [
    F_TITLE, F_DESCRIPTION, F_STATE, F_PRIORITY, F_ASSIGNED, F_POINTS, F_ACCEPTANCE,
    F_EFFORT, F_ESTIMATE, F_REPRO, F_TYPE, F_AREA, F_ITERATION,
    F_STATE_CHANGED, F_CHANGED, F_TAGS,
]

# Work item types that carry the Acceptance Criteria field. Writing a field the
# type doesn't define rejects the WHOLE json-patch, so pushes only include it
# for these types (reads are always safe — absent fields are just omitted).
ACCEPTANCE_CRITERIA_TYPES = {"User Story", "Product Backlog Item", "Bug", "Requirement"}

def _iso_date(value: str | None) -> date | None:
    """Parse an Azure DevOps ISO timestamp ("2026-08-02T00:00:00Z") to a date."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _plain_text(value: str | None, limit: int = 1000) -> str | None:
    """ADO rich-text fields are HTML; reports need the words."""
    if not value:
        return None
    text = re.sub(r"<(br|/p|/div|/li)\b[^>]*>", "\n", value, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(line for line in lines if line).strip()
    return text[:limit] or None


def _iso_datetime(value: str | None) -> datetime | None:
    """Parse an Azure DevOps ISO timestamp to an aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


logger = logging.getLogger(__name__)

# tasks.title is VARCHAR(255) (migration 014), matching the Azure DevOps
# System.Title limit. Clamp here anyway: the import runs as ONE transaction, so
# a single overlong title would otherwise abort the entire sync.
MAX_TITLE_LEN = 255

# States already reported as unmapped — keeps the warning to once per process.
_UNMAPPED_STATES_SEEN: set[str] = set()


class TFSTaskProvider(TaskProvider):
    """TaskProvider backed by Azure DevOps / TFS work items."""

    def __init__(
        self,
        org_url: str,
        project: str,
        pat: str,
        work_item_type: str = "Task",
        timeout: float = 30.0,
        read_only: bool = False,
        api_version: str = API_VERSION,
        area_path: str = "",
        max_items: int = 0,
        sync_types: tuple[str, ...] | None = None,
    ) -> None:
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.work_item_type = work_item_type
        self.timeout = timeout
        self.read_only = read_only
        self.api_version = api_version
        self.area_path = area_path.strip()
        self.max_items = max_items
        self.sync_types = (
            DEFAULT_SYNC_TYPES if sync_types is None else tuple(sync_types)
        )
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._auth_header = f"Basic {token}"

    def _guard_write(self, op: str) -> None:
        """Hard stop on any mutation when the provider is read-only."""
        if self.read_only:
            raise ReadOnlyProviderError(
                f"{op} blocked: TFS provider is read-only "
                f"(set PUSH_ENABLED=true to allow writes to {self.org_url})"
            )

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Authorization": self._auth_header},
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError("Azure DevOps rate limit exceeded", retry_after=retry_after)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Azure DevOps API error {resp.status_code}: {resp.text[:500]}"
            )

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    @staticmethod
    def _map_state(state: str) -> str:
        """ADO state -> our status, case-insensitively.

        Unknown states land in "backlog" (the pre-existing behaviour) but are
        logged once each, so a customised process surfaces in the logs instead
        of silently collapsing the board into one column.
        """
        key = (state or "").strip().lower()
        mapped = STATE_TO_STATUS.get(key)
        if mapped is None:
            if key and key not in _UNMAPPED_STATES_SEEN:
                _UNMAPPED_STATES_SEEN.add(key)
                logger.warning(
                    "Unmapped Azure DevOps state %r -> defaulting to 'backlog'. "
                    "Add it to STATE_TO_STATUS in tfs_task_provider.py.", state,
                )
            return "backlog"
        return mapped

    @staticmethod
    def _to_external(work_item: dict) -> ExternalTask:
        fields = work_item.get("fields", {})
        assigned = fields.get(F_ASSIGNED)
        assignee_name = None
        assignee_external_id = None
        if isinstance(assigned, dict):
            assignee_name = assigned.get("displayName")
            # The identity GUID is the reliable key; display names vary in
            # spelling across the instance and do not survive a rename.
            assignee_external_id = assigned.get("id")
        elif isinstance(assigned, str):
            assignee_name = assigned

        # Story points: Agile uses StoryPoints, Scrum uses Effort on the PBI.
        points = fields.get(F_POINTS)
        if points is None:
            points = fields.get(F_EFFORT)
        # Tasks are estimated in hours instead.
        estimate = fields.get(F_ESTIMATE)

        # Bugs and Issues put their detail in ReproSteps; everything else in
        # Description. Fall back so neither type imports as an empty shell.
        description = fields.get(F_DESCRIPTION) or fields.get(F_REPRO)

        title = fields.get(F_TITLE, "") or ""
        if len(title) > MAX_TITLE_LEN:
            logger.warning(
                "Work item %s: title of %d chars truncated to %d",
                work_item.get("id"), len(title), MAX_TITLE_LEN,
            )
            title = title[:MAX_TITLE_LEN]

        # Area path is "<Project>\<Stream>\<SubProject>". The configured
        # TFS_AREA_PATH is the stream root, so anything deeper is the project;
        # items sitting directly on the stream root have no project.
        area = fields.get(F_AREA) or None
        iteration = fields.get(F_ITERATION) or None
        area_parts = area.split("\\") if area else []
        project_name = area_parts[2] if len(area_parts) > 2 else None

        return ExternalTask(
            external_id=str(work_item["id"]),
            title=title,
            area_path=area,
            project_name=project_name,
            iteration_path=iteration,
            sprint_name=iteration.split("\\")[-1] if iteration else None,
            work_item_type=fields.get(F_TYPE),
            description=description,
            acceptance_criteria=fields.get(F_ACCEPTANCE),
            status=TFSTaskProvider._map_state(fields.get(F_STATE, "")),
            priority=ADO_TO_PRIORITY.get(fields.get(F_PRIORITY), "medium"),
            assignee_name=assignee_name,
            assignee_external_id=assignee_external_id,
            story_points=int(points) if points is not None else None,
            estimated_hours=round(float(estimate)) if estimate is not None else None,
            external_state=(fields.get(F_STATE) or None),
            state_changed_at=_iso_datetime(fields.get(F_STATE_CHANGED)),
            external_changed_at=_iso_datetime(fields.get(F_CHANGED)),
            tags=(fields.get(F_TAGS) or None) and str(fields.get(F_TAGS))[:500],
            hold_reason=_plain_text(fields.get(F_WHY_ON_HOLD)),
        )

    def _patch_ops(self, data: ExternalTaskCreate | ExternalTaskUpdate) -> list[dict]:
        """Build a JSON-Patch document for create/update (op 'add' upserts)."""
        ops: list[dict] = []

        def add(path: str, value: object) -> None:
            ops.append({"op": "add", "path": path, "value": value})

        if data.title is not None:
            add(f"/fields/{F_TITLE}", data.title)
        if data.description is not None:
            add(f"/fields/{F_DESCRIPTION}", data.description)
        if (
            data.acceptance_criteria is not None
            and self.work_item_type in ACCEPTANCE_CRITERIA_TYPES
        ):
            add(f"/fields/{F_ACCEPTANCE}", data.acceptance_criteria)
        if data.status is not None:
            add(f"/fields/{F_STATE}", STATUS_TO_STATE.get(data.status, "New"))
        if data.priority is not None:
            add(f"/fields/{F_PRIORITY}", PRIORITY_TO_ADO.get(data.priority, 3))
        if data.assignee_name is not None:
            add(f"/fields/{F_ASSIGNED}", data.assignee_name)
        if data.story_points is not None:
            add(f"/fields/{F_POINTS}", data.story_points)
        return ops

    # ------------------------------------------------------------------
    # TaskProvider interface
    # ------------------------------------------------------------------
    @staticmethod
    def _wiql_literal(value: str) -> str:
        """Escape a value for use inside a single-quoted WIQL literal."""
        return value.replace("'", "''")

    async def _query_ids(self, client: httpx.AsyncClient) -> list[int]:
        """Run a WIQL query and return matching work item ids (newest first).

        Scoped by ``area_path`` when set — a real instance can hold tens of
        thousands of work items, and an unscoped pull would both hammer the
        server and flood our DB.
        """
        where = [f"[System.TeamProject] = '{self._wiql_literal(self.project)}'"]
        if self.area_path:
            where.append(
                f"[System.AreaPath] UNDER '{self._wiql_literal(self.area_path)}'"
            )
        if self.sync_types:
            joined = ", ".join(
                f"'{self._wiql_literal(t)}'" for t in self.sync_types
            )
            where.append(f"[System.WorkItemType] IN ({joined})")
        for state in EXCLUDED_STATES:
            where.append(f"[System.State] <> '{self._wiql_literal(state)}'")
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY [System.ChangedDate] DESC"
            )
        }
        url = f"{self.org_url}/{self.project}/_apis/wit/wiql?api-version={self.api_version}"
        try:
            resp = await client.post(url, json=wiql)
        except httpx.TimeoutException as exc:
            raise TaskProviderTimeoutError("WIQL query timed out") from exc
        self._raise_for_status(resp)
        ids = [row["id"] for row in resp.json().get("workItems", [])]
        # Newest-changed first, so the cap keeps the most recently active items.
        return ids[: self.max_items] if self.max_items > 0 else ids

    async def _fetch_batch(
        self, client: httpx.AsyncClient, ids: list[int]
    ) -> list[ExternalTask]:
        if not ids:
            return []
        url = f"{self.org_url}/_apis/wit/workitemsbatch?api-version={self.api_version}"
        body = {"ids": ids, "fields": FETCH_FIELDS}
        try:
            resp = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise TaskProviderTimeoutError("Work item batch fetch timed out") from exc
        self._raise_for_status(resp)
        return [self._to_external(wi) for wi in resp.json().get("value", [])]

    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        async with self._client() as client:
            ids = await self._query_ids(client)
            total = len(ids)
            start = (page - 1) * page_size
            end = start + page_size
            items = await self._fetch_batch(client, ids[start:end])
            return TaskPage(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                has_more=end < total,
            )

    async def get_task(self, external_id: str) -> ExternalTask | None:
        url = (
            f"{self.org_url}/_apis/wit/workitems/{external_id}"
            f"?fields={','.join(FETCH_FIELDS)}&api-version={self.api_version}"
        )
        async with self._client() as client:
            try:
                resp = await client.get(url)
            except httpx.TimeoutException as exc:
                raise TaskProviderTimeoutError("get_task timed out") from exc
            if resp.status_code == 404:
                return None
            self._raise_for_status(resp)
            return self._to_external(resp.json())

    async def sync_tasks(self) -> list[ExternalTask]:
        async with self._client() as client:
            ids = await self._query_ids(client)
            results: list[ExternalTask] = []
            # Azure DevOps caps workitemsbatch at 200 ids per request.
            for i in range(0, len(ids), 200):
                results.extend(await self._fetch_batch(client, ids[i : i + 200]))
            return results

    async def list_sprints(self) -> list[ExternalSprint]:
        """Flatten the project's iteration classification tree into sprints.

        Leaf nodes are the actual sprints; parents are just grouping folders.
        """
        url = (
            f"{self.org_url}/{self.project}/_apis/wit/classificationnodes/"
            f"iterations?$depth=5&api-version={self.api_version}"
        )
        async with self._client() as client:
            try:
                resp = await client.get(url)
            except httpx.TimeoutException as exc:
                raise TaskProviderTimeoutError("list_sprints timed out") from exc
            self._raise_for_status(resp)
            root = resp.json()

        sprints: list[ExternalSprint] = []

        def walk(node: dict, prefix: str = "") -> None:
            path = f"{prefix}\\{node['name']}" if prefix else node["name"]
            children = node.get("children") or []
            if not children:
                attrs = node.get("attributes") or {}
                sprints.append(
                    ExternalSprint(
                        name=node["name"],
                        path=path,
                        start_date=_iso_date(attrs.get("startDate")),
                        end_date=_iso_date(attrs.get("finishDate")),
                    )
                )
            for child in children:
                walk(child, path)

        walk(root)
        return sprints

    async def create_task(self, task: ExternalTaskCreate) -> ExternalTask:
        self._guard_write("create_task")
        url = (
            f"{self.org_url}/{self.project}/_apis/wit/workitems/"
            f"${self.work_item_type}?api-version={self.api_version}"
        )
        async with self._client() as client:
            try:
                resp = await client.post(
                    url,
                    headers={"Content-Type": "application/json-patch+json"},
                    json=self._patch_ops(task),
                )
            except httpx.TimeoutException as exc:
                raise TaskProviderTimeoutError("create_task timed out") from exc
            self._raise_for_status(resp)
            return self._to_external(resp.json())

    async def update_task(
        self, external_id: str, changes: ExternalTaskUpdate
    ) -> ExternalTask:
        self._guard_write("update_task")
        url = (
            f"{self.org_url}/_apis/wit/workitems/{external_id}"
            f"?api-version={self.api_version}"
        )
        async with self._client() as client:
            try:
                resp = await client.patch(
                    url,
                    headers={"Content-Type": "application/json-patch+json"},
                    json=self._patch_ops(changes),
                )
            except httpx.TimeoutException as exc:
                raise TaskProviderTimeoutError("update_task timed out") from exc
            self._raise_for_status(resp)
            return self._to_external(resp.json())
