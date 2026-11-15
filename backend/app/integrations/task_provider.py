"""Abstract TaskProvider interface for pluggable integration layer.

This interface is designed based on real Azure DevOps API patterns:
- Pagination with page/page_size
- External IDs for deduplication
- Rate limits and timeouts as expected behaviors

The abstract interface ensures v2 Azure DevOps integration is a swap, not a rewrite.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class ExternalTask(BaseModel):
    """
    External task representation from integrated system.

    This represents a task as it exists in the external system (e.g., Azure DevOps),
    which may have different fields/structure than our internal Task model.
    """

    external_id: str
    title: str
    # Grouping, straight from the provider. Azure DevOps area and iteration are
    # independent axes: area is the stream/project split, iteration is the
    # sprint. Carried raw so the import layer decides how to model them.
    area_path: str | None = None        # e.g. "Northwind\\Retail Platform\\Storefront"
    project_name: str | None = None     # leaf of area_path, e.g. "Storefront"
    iteration_path: str | None = None   # e.g. "Northwind\\Sprint 2403"
    sprint_name: str | None = None      # leaf of iteration_path, e.g. "Sprint 2403"
    # Azure DevOps type: "Bug", "Issue", "Task", "Product Backlog Item", ...
    # Carried so the board can tell a defect from a feature; the provider
    # already filters on it, we just used to discard it after filtering.
    work_item_type: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Literal["backlog", "todo", "in_progress", "review", "done"] = "backlog"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    assignee_name: str | None = None
    # Stable identity of the assignee. Display names are not a reliable key on a
    # real instance, so the import matches on this first and falls back to name.
    assignee_external_id: str | None = None
    story_points: int | None = None
    # Hours. Scrum shops often estimate Tasks in hours (OriginalEstimate)
    # rather than points, so both are carried.
    estimated_hours: int | None = None
    # Raw provider signals for blocker detection (status above is lossy).
    external_state: str | None = None       # e.g. "On Hold"
    state_changed_at: datetime | None = None
    external_changed_at: datetime | None = None
    tags: str | None = None
    hold_reason: str | None = None


class ExternalTaskCreate(BaseModel):
    """Payload for creating a task in the external system (push)."""

    title: str
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Literal["backlog", "todo", "in_progress", "review", "done"] = "backlog"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    assignee_name: str | None = None
    story_points: int | None = None
    # Hours. Scrum shops often estimate Tasks in hours (OriginalEstimate)
    # rather than points, so both are carried.
    estimated_hours: int | None = None


class ExternalTaskUpdate(BaseModel):
    """Partial payload for updating a task in the external system (push)."""

    title: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Literal["backlog", "todo", "in_progress", "review", "done"] | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    assignee_name: str | None = None
    story_points: int | None = None
    # Hours. Scrum shops often estimate Tasks in hours (OriginalEstimate)
    # rather than points, so both are carried.
    estimated_hours: int | None = None


class ExternalSprint(BaseModel):
    """An iteration in the external system, used to build local Sprint rows.

    ``path`` is the full iteration path and is the stable key; ``name`` is the
    leaf, which is what ExternalTask.sprint_name carries.
    """

    name: str
    path: str
    start_date: date | None = None
    end_date: date | None = None


class ExternalTeamMember(BaseModel):
    """A person on the external system's team, used to build TeamMember rows.

    ``external_id`` is the identity GUID and the stable key. ``email`` is often
    absent on an on-prem, AD-backed instance — the accounts are domain logins
    (``northwind\\jklein``) — so the import synthesises one when it is missing.
    ``capacity_hours_per_sprint`` is None unless the team fills in the sprint
    Capacity tab.
    """

    external_id: str
    name: str
    unique_name: str | None = None
    email: str | None = None
    role: str | None = None
    capacity_hours_per_sprint: int | None = None


class TaskPage(BaseModel):
    """Paginated response for task listing from external system."""

    items: list[ExternalTask]
    total: int
    page: int
    page_size: int
    has_more: bool


class RateLimitError(Exception):
    """Raised when external API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class TaskProviderTimeoutError(Exception):
    """Raised when external API request times out."""

    pass


class ReadOnlyProviderError(Exception):
    """Raised when a write is attempted against a read-only provider.

    The guard lives in the provider itself rather than only at the call sites
    so that *any* code path — a Celery task, an API handler, autopilot, or
    something added later — fails loudly instead of mutating the external
    system. Connecting to a real production instance is the case this exists
    for; see ``PUSH_ENABLED`` in the repo-root ``.env``.
    """

    pass


class TaskProvider(ABC):
    """
    Abstract base class for task providers.

    Implementations should handle:
    - Pagination (Azure DevOps uses continuation tokens, mapped to page/page_size)
    - Rate limiting (return RateLimitError with retry_after)
    - Timeouts (return TaskProviderTimeoutError)
    - Authentication (implementation-specific)

    v1: MockTaskProvider (generates sample data)
    v2: AzureDevOpsTaskProvider (real integration)
    """

    @abstractmethod
    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        """
        List tasks from external system with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page (max 50 for most APIs)

        Returns:
            TaskPage with items and pagination info

        Raises:
            RateLimitError: When API rate limit exceeded
            TaskProviderTimeoutError: When request times out
        """
        pass

    @abstractmethod
    async def get_task(self, external_id: str) -> ExternalTask | None:
        """
        Get a single task by external ID.

        Args:
            external_id: The task ID in the external system

        Returns:
            ExternalTask if found, None otherwise

        Raises:
            RateLimitError: When API rate limit exceeded
            TaskProviderTimeoutError: When request times out
        """
        pass

    @abstractmethod
    async def sync_tasks(self) -> list[ExternalTask]:
        """
        Fetch all tasks from external system for import.

        This method handles pagination internally and returns all tasks.
        Use for initial sync or periodic refresh.

        Returns:
            List of all ExternalTask objects from the system

        Raises:
            RateLimitError: When API rate limit exceeded
            TaskProviderTimeoutError: When request times out
        """
        pass

    async def list_sprints(self) -> list["ExternalSprint"]:
        """Iterations/sprints defined in the external system.

        Not abstract: providers without a sprint concept (the mock) inherit the
        empty default and the import simply leaves tasks unassigned.
        """
        return []

    async def list_team_members(self) -> list["ExternalTeamMember"]:
        """People on the external system's team.

        Not abstract, for the same reason as list_sprints: a provider with no
        team concept inherits the empty default, and the import falls back to
        matching assignees by display name.
        """
        return []

    @abstractmethod
    async def create_task(self, task: ExternalTaskCreate) -> ExternalTask:
        """
        Create a task in the external system (push).

        Args:
            task: The task fields to create.

        Returns:
            The created ExternalTask, carrying the provider-assigned external_id.

        Raises:
            RateLimitError: When API rate limit exceeded
            TaskProviderTimeoutError: When request times out
        """
        pass

    @abstractmethod
    async def update_task(
        self, external_id: str, changes: ExternalTaskUpdate
    ) -> ExternalTask:
        """
        Update an existing task in the external system (push).

        Args:
            external_id: The task ID in the external system.
            changes: Partial fields to update (None fields are left untouched).

        Returns:
            The updated ExternalTask.

        Raises:
            RateLimitError: When API rate limit exceeded
            TaskProviderTimeoutError: When request times out
        """
        pass
