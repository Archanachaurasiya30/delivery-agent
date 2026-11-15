"""Task management service layer."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.task_provider import TaskProvider
from app.models.sprint import Sprint
from app.models.stream import Stream
from app.models.task import Task
from app.models.team import TeamMember
from app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


class TaskService:
    """Service class for task operations with business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 50,
        status_filter: str | None = None,
        priority_filter: str | None = None,
        assignee_id: UUID | None = None,
    ) -> tuple[list[Task], int]:
        """
        List tasks with pagination and optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Filter by status (optional)
            priority_filter: Filter by priority (optional)
            assignee_id: Filter by assignee (optional)

        Returns:
            Tuple of (list of tasks, total count)
        """
        # Build base query with filters
        base_query = select(Task)

        if status_filter:
            base_query = base_query.where(Task.status == status_filter)
        if priority_filter:
            base_query = base_query.where(Task.priority == priority_filter)
        if assignee_id:
            base_query = base_query.where(Task.assignee_id == assignee_id)

        # Get total count with filters
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated tasks
        query = base_query.offset(skip).limit(limit).order_by(Task.created_at.desc())
        result = await self.db.execute(query)
        tasks = list(result.scalars().all())

        return tasks, total

    async def get_task(self, task_id: UUID) -> Task:
        """
        Get a task by ID.

        Args:
            task_id: UUID of the task

        Returns:
            Task instance

        Raises:
            HTTPException: 404 if task not found
        """
        query = select(Task).where(Task.id == task_id)
        result = await self.db.execute(query)
        task = result.scalar_one_or_none()

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found",
            )

        return task

    async def create_task(self, data: TaskCreate) -> Task:
        """
        Create a new task.

        Args:
            data: Task creation data

        Returns:
            Created Task instance

        Raises:
            HTTPException: 404 if assignee_id provided but team member not found
        """
        # Verify assignee exists if provided
        if data.assignee_id:
            query = select(TeamMember).where(TeamMember.id == data.assignee_id)
            result = await self.db.execute(query)
            assignee = result.scalar_one_or_none()

            if assignee is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team member with id {data.assignee_id} not found",
                )

        # Convert UUID to string for database
        task_data = data.model_dump()
        if task_data.get("assignee_id"):
            task_data["assignee_id"] = str(task_data["assignee_id"])

        task = Task(**task_data)
        self.db.add(task)
        await self.db.flush()

        return task

    async def update_task(self, task_id: UUID, data: TaskUpdate) -> Task:
        """
        Update a task with partial data.

        Args:
            task_id: UUID of the task
            data: Partial update data

        Returns:
            Updated Task instance

        Raises:
            HTTPException: 404 if task or assignee not found
        """
        task = await self.get_task(task_id)

        # Verify assignee exists if being updated
        update_data = data.model_dump(exclude_unset=True)
        if "assignee_id" in update_data and update_data["assignee_id"]:
            query = select(TeamMember).where(TeamMember.id == update_data["assignee_id"])
            result = await self.db.execute(query)
            assignee = result.scalar_one_or_none()

            if assignee is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team member with id {update_data['assignee_id']} not found",
                )
            # Convert UUID to string for database
            update_data["assignee_id"] = str(update_data["assignee_id"])

        # Capture the old status BEFORE the setattr loop overwrites it.
        previous_status = task.status

        # Apply only provided fields
        for field, value in update_data.items():
            setattr(task, field, value)

        if task.status != previous_status:
            self.record_status_change(task, previous_status, task.status, source="api")

        await self.db.flush()

        return task

    def record_status_change(
        self,
        task: Task,
        from_status: str | None,
        to_status: str,
        source: str = "api",
        changed_by: str | None = None,
    ) -> None:
        """Append a transition to the flow event log.

        Explicit at each call site rather than an ORM ``before_flush`` hook:
        there are only three writers, and a listener would silently start
        recording (or silently stop) as unrelated code changes.

        Adds to the session; the caller's flush persists it.
        """
        from app.models.task_status_event import TaskStatusEvent

        self.db.add(
            TaskStatusEvent(
                task_id=str(task.id),
                from_status=from_status,
                to_status=to_status,
                changed_at=datetime.now(timezone.utc),
                source=source,
                changed_by=changed_by,
            )
        )

    async def delete_task(self, task_id: UUID) -> None:
        """
        Delete a task.

        Args:
            task_id: UUID of the task

        Raises:
            HTTPException: 404 if task not found
        """
        task = await self.get_task(task_id)
        await self.db.delete(task)
        await self.db.flush()

    async def get_summary(self) -> dict:
        """
        Get task summary with counts by status and priority.

        Returns:
            Dictionary with total, by_status, and by_priority counts
        """
        # Counted in SQL rather than by loading every row — this is polled by
        # the dashboards. Response shape is unchanged.
        status_rows = await self.db.execute(
            select(Task.status, func.count(Task.id)).group_by(Task.status)
        )
        by_status = [
            {"status": status, "count": count} for status, count in status_rows.all()
        ]

        priority_rows = await self.db.execute(
            select(Task.priority, func.count(Task.id)).group_by(Task.priority)
        )
        priority_counts = {priority: count for priority, count in priority_rows.all()}

        return {
            "total": sum(row["count"] for row in by_status),
            "by_status": by_status,
            "by_priority": priority_counts,
        }

    async def import_from_provider(
        self, provider: TaskProvider, source_label: str = "external"
    ) -> dict[str, list[Task]]:
        """
        Upsert tasks from an external provider.

        Deduplicates on external_id: new external tasks are inserted, existing
        ones have their mutable fields updated when they changed. Imported tasks
        are marked with ``source=source_label`` and ``last_synced_at`` so the
        push pipeline never sends them back (avoids the push<->pull echo loop).

        Args:
            provider: TaskProvider implementation.
            source_label: Provenance to stamp on touched rows ("mock"/"tfs").

        Returns:
            {"inserted": [...], "updated": [...]} lists of Task instances.
        """
        external_tasks = await provider.sync_tasks()
        sprint_ids = await self._sync_sprints(provider, external_tasks)
        member_ids = await self._sync_team_members(provider)

        # Existing tasks keyed by external_id (full rows so we can update them).
        existing_query = select(Task).where(Task.external_id.isnot(None))
        existing_result = await self.db.execute(existing_query)
        existing_by_external = {
            t.external_id: t for t in existing_result.scalars().all()
        }

        # Best-effort assignee name -> id mapping (case-insensitive).
        name_to_id = await self._assignee_name_map()

        now = datetime.now(timezone.utc)
        inserted: list[Task] = []
        updated: list[Task] = []

        for ext in external_tasks:
            # Identity id first — display names vary in spelling on a real
            # instance and match nothing. Name is the fallback for providers
            # that carry no identity (the mock).
            assignee_id = member_ids.get(ext.assignee_external_id or "") or name_to_id.get(
                (ext.assignee_name or "").strip().lower()
            )
            existing = existing_by_external.get(ext.external_id)

            if existing is None:
                task = Task(
                    title=ext.title,
                    description=ext.description,
                    acceptance_criteria=ext.acceptance_criteria,
                    status=ext.status,
                    priority=ext.priority,
                    story_points=ext.story_points,
                    estimated_hours=ext.estimated_hours,
                    project_name=ext.project_name,
                    work_item_type=ext.work_item_type,
                    external_state=ext.external_state,
                    state_changed_at=ext.state_changed_at,
                    external_changed_at=ext.external_changed_at,
                    tags=ext.tags,
                    hold_reason=ext.hold_reason,
                    sprint_id=sprint_ids.get(ext.sprint_name or ""),
                    external_id=ext.external_id,
                    assignee_id=assignee_id,
                    source=source_label,
                    last_synced_at=now,
                )
                self.db.add(task)
                inserted.append(task)
                continue

            # Update only changed mutable fields to avoid churn.
            changed = False
            previous_status = existing.status
            for field, value in (
                ("title", ext.title),
                ("description", ext.description),
                ("acceptance_criteria", ext.acceptance_criteria),
                ("status", ext.status),
                ("priority", ext.priority),
                ("story_points", ext.story_points),
                ("estimated_hours", ext.estimated_hours),
                ("project_name", ext.project_name),
                ("work_item_type", ext.work_item_type),
                ("external_state", ext.external_state),
                ("state_changed_at", ext.state_changed_at),
                ("external_changed_at", ext.external_changed_at),
                ("tags", ext.tags),
                ("hold_reason", ext.hold_reason),
            ):
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            if assignee_id and existing.assignee_id != assignee_id:
                existing.assignee_id = assignee_id
                changed = True
            # Work items move between iterations; follow them.
            new_sprint_id = sprint_ids.get(ext.sprint_name or "")
            if new_sprint_id and existing.sprint_id != new_sprint_id:
                existing.sprint_id = new_sprint_id
                changed = True

            if changed:
                if existing.status != previous_status:
                    self.record_status_change(
                        existing, previous_status, existing.status, source="sync"
                    )
                existing.last_synced_at = now
                updated.append(existing)

        if inserted or updated:
            await self.db.flush()

        return {"inserted": inserted, "updated": updated}

    async def _sync_sprints(
        self, provider: TaskProvider, external_tasks: list
    ) -> dict[str, str]:
        """Upsert local Sprints for the iterations the imported tasks reference.

        Returns a ``{sprint_name: sprint_id}`` map for linking tasks.

        Only iterations that actually carry work are created: a real instance
        defines a rolling calendar of them (146 on the Northwind server) and
        materialising the empty ones would bury the board in noise.
        """
        wanted = {t.sprint_name for t in external_tasks if t.sprint_name}
        if not wanted:
            return {}

        try:
            available = await provider.list_sprints()
        except Exception as exc:  # noqa: BLE001 - sprints are best-effort
            logger.warning("Could not list sprints from provider: %s", exc)
            return {}

        by_name = {s.name: s for s in available if s.name in wanted}
        if not by_name:
            return {}

        existing_rows = await self.db.execute(
            select(Sprint).where(Sprint.name.in_(by_name.keys()))
        )
        existing = {s.name: s for s in existing_rows.scalars().all()}

        stream_id = await self._external_stream_id()
        today = datetime.now(timezone.utc).date()
        touched: dict[str, Sprint] = {}

        for name, ext in by_name.items():
            # start/end are NOT NULL on Sprint; fall back to a nominal
            # two-week window when the server leaves the dates unset.
            start = ext.start_date or today
            end = ext.end_date or start + timedelta(days=14)
            if end < today:
                status = "completed"
            elif start <= today <= end:
                status = "active"
            else:
                status = "planning"

            sprint = existing.get(name)
            if sprint is None:
                sprint = Sprint(
                    name=name,
                    start_date=start,
                    end_date=end,
                    status=status,
                    stream_id=stream_id,
                )
                self.db.add(sprint)
            else:
                sprint.start_date = start
                sprint.end_date = end
                sprint.status = status
                if stream_id and sprint.stream_id is None:
                    sprint.stream_id = stream_id
            touched[name] = sprint

        # Flush FIRST: a pending Sprint has no id until the insert runs, so
        # reading .id before this point yields None and every task would be
        # linked to nothing.
        await self.db.flush()

        mapping = {name: sprint.id for name, sprint in touched.items()}
        logger.info(
            "Synced %d sprints (%d new)", len(mapping), len(mapping) - len(existing)
        )
        return mapping

    async def _sync_team_members(self, provider: TaskProvider) -> dict[str, str]:
        """Upsert local TeamMembers from the provider's roster.

        Returns an ``{external_id: team_member_id}`` map for linking assignees.

        Keyed on the identity id, never the name: the seeded rows are near
        misses of real people ("Diego Alvarez" vs "Diego Álvarez"), so
        name matching resolved nothing and every synced task imported
        unassigned. Locally created members (external_id NULL) are left alone.
        """
        try:
            roster = await provider.list_team_members()
        except Exception as exc:  # noqa: BLE001 - roster is best-effort
            logger.warning("Could not list team members from provider: %s", exc)
            return {}
        if not roster:
            return {}

        existing_rows = await self.db.execute(
            select(TeamMember).where(TeamMember.external_id.isnot(None))
        )
        existing = {m.external_id: m for m in existing_rows.scalars().all()}

        # email is NOT NULL UNIQUE, but an AD-backed instance has no addresses
        # to give us, so one is synthesised and has to stay collision-free.
        taken_rows = await self.db.execute(select(TeamMember.email))
        taken = {e.lower() for e in taken_rows.scalars().all() if e}

        created = 0
        for ext in roster:
            member = existing.get(ext.external_id)
            if member is None:
                email = self._synth_email(ext, taken)
                taken.add(email.lower())
                member = TeamMember(
                    name=ext.name[:100],
                    email=email,
                    role=ext.role or "developer",
                    external_id=ext.external_id,
                )
                if ext.capacity_hours_per_sprint:
                    member.capacity_hours_per_sprint = ext.capacity_hours_per_sprint
                self.db.add(member)
                existing[ext.external_id] = member
                created += 1
                continue

            # Follow renames, and take capacity only when the server has it —
            # an absent Capacity tab must not overwrite a value set locally.
            if member.name != ext.name[:100]:
                member.name = ext.name[:100]
            if ext.capacity_hours_per_sprint:
                member.capacity_hours_per_sprint = ext.capacity_hours_per_sprint

        # Flush FIRST: a pending TeamMember has no id until the insert runs, so
        # reading .id before this point yields None and no task would link.
        await self.db.flush()

        mapping = {ext_id: m.id for ext_id, m in existing.items()}
        logger.info(
            "Synced %d team members (%d new)", len(roster), created
        )
        return mapping

    @staticmethod
    def _synth_email(ext, taken: set[str]) -> str:
        """Build a stable, unique local address for a person with no email.

        On-prem accounts look like ``northwind\\jklein``; the login is the stable
        part, so it becomes the local part. Matches the ``@delivery.local``
        convention the seeded rows already use.
        """
        raw = (ext.unique_name or ext.name or ext.external_id).strip()
        local = raw.split("\\")[-1].split("@")[0]
        local = "".join(c for c in local.lower() if c.isalnum() or c in "._-")
        local = local or f"user{ext.external_id[:8]}"

        email = f"{local}@delivery.local"
        if email.lower() not in taken:
            return email
        # Two accounts can normalise to the same local part; the identity id
        # disambiguates without inventing a different-looking person.
        return f"{local}.{ext.external_id[:8]}@delivery.local"

    async def _external_stream_id(self) -> str | None:
        """Get/create the stream the synced area path represents.

        TFS_AREA_PATH is the stream root (e.g. "Northwind\\Retail
        Platform"); its leaf names the stream. Anything deeper in the area
        path is a project *within* that stream, not a stream of its own.
        """
        area = (settings.tfs_area_path or "").strip().strip("'\"")
        if not area:
            return None
        name = area.split("\\")[-1].strip()
        if not name:
            return None

        found = await self.db.execute(select(Stream).where(Stream.name == name))
        stream = found.scalar_one_or_none()
        if stream is None:
            stream = Stream(name=name, description=f"Synced from area path {area}")
            self.db.add(stream)
            await self.db.flush()
        return stream.id

    async def _assignee_name_map(self) -> dict[str, str]:
        """Map lowercased team-member names to their ids (best-effort)."""
        result = await self.db.execute(select(TeamMember.id, TeamMember.name))
        return {name.strip().lower(): mid for mid, name in result.all() if name}
