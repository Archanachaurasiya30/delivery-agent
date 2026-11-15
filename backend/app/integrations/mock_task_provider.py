"""Mock TaskProvider implementation for v1 development and testing.

Generates realistic sample tasks and simulates failure modes that would
occur with real APIs (rate limits, timeouts). Per RESEARCH Pitfall 8:
"Design integration interface based on real API docs, not mock capabilities."
"""

import asyncio
import random
import uuid

from app.integrations.task_provider import (
    ExternalTask,
    ExternalTaskCreate,
    ExternalTaskUpdate,
    RateLimitError,
    TaskPage,
    TaskProvider,
    TaskProviderTimeoutError,
)


# Realistic software development task templates
TASK_TEMPLATES = [
    # Feature development
    ("Implement user authentication", "Add login/logout functionality with JWT tokens", "todo", "high"),
    ("Add export to CSV feature", "Allow users to export task data to CSV format", "backlog", "medium"),
    ("Create dashboard analytics", "Build charts showing sprint velocity and burndown", "backlog", "high"),
    ("Implement notification system", "Real-time notifications for task updates", "todo", "medium"),
    ("Add dark mode support", "Implement theme switching between light and dark modes", "backlog", "low"),
    ("Build search functionality", "Full-text search across tasks and descriptions", "in_progress", "high"),
    ("Create mobile responsive layout", "Ensure UI works well on mobile devices", "todo", "medium"),
    ("Implement drag-and-drop", "Allow reordering tasks via drag-and-drop", "backlog", "low"),
    ("Add file attachment support", "Allow users to attach files to tasks", "backlog", "medium"),
    ("Build API rate limiting", "Implement rate limiting for public API endpoints", "review", "critical"),
    # Bug fixes
    ("Fix pagination bug", "Pagination shows wrong total count on filtered results", "in_progress", "high"),
    ("Fix memory leak in WebSocket", "WebSocket connections not properly cleaned up", "todo", "critical"),
    ("Resolve timezone issues", "Dates displaying incorrectly for non-UTC timezones", "backlog", "medium"),
    ("Fix broken email notifications", "Email notifications not sending for new tasks", "review", "high"),
    ("Fix CSS overflow on long titles", "Long task titles break card layout", "done", "low"),
    # Technical debt
    ("Refactor database queries", "Optimize slow queries identified in APM", "backlog", "medium"),
    ("Update dependency versions", "Update outdated npm and pip packages", "todo", "low"),
    ("Add comprehensive logging", "Improve logging for debugging production issues", "in_progress", "medium"),
    ("Write integration tests", "Add API integration tests for critical paths", "backlog", "high"),
    ("Document API endpoints", "Create OpenAPI documentation for all endpoints", "done", "medium"),
]

ASSIGNEE_NAMES = [
    "Alice Chen",
    "Bob Smith",
    "Carol Johnson",
    "David Kim",
    "Eva Martinez",
    None,  # Some tasks unassigned
    None,
]


class MockTaskProvider(TaskProvider):
    """
    Mock implementation that generates realistic sample tasks.

    Simulates real API behavior including:
    - 1% chance of RateLimitError
    - 0.5% chance of timeout
    - Proper pagination support

    This is NOT a database-backed provider - it generates data in memory.
    """

    def __init__(self, task_count: int = 20, failure_rate: float = 0.01):
        """
        Initialize mock provider.

        Args:
            task_count: Number of mock tasks to generate (15-20 typical)
            failure_rate: Probability of simulated failures (0.01 = 1%)
        """
        self.failure_rate = failure_rate
        self._tasks = self._generate_tasks(task_count)

    def _generate_tasks(self, count: int) -> list[ExternalTask]:
        """Generate a list of realistic mock tasks."""
        tasks = []
        templates = random.sample(TASK_TEMPLATES, min(count, len(TASK_TEMPLATES)))

        for i, (title, description, status, priority) in enumerate(templates):
            task = ExternalTask(
                external_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
                title=title,
                description=description,
                status=status,
                priority=priority,
                assignee_name=random.choice(ASSIGNEE_NAMES),
                story_points=random.choice([1, 2, 3, 5, 8, 13, None]),
            )
            tasks.append(task)

        return tasks

    async def _simulate_api_latency(self) -> None:
        """Simulate network latency and potential failures."""
        # Simulate network latency (50-200ms)
        await asyncio.sleep(random.uniform(0.05, 0.2))

        # Simulate rate limit (1% chance)
        if random.random() < self.failure_rate:
            raise RateLimitError("Rate limit exceeded", retry_after=60)

        # Simulate timeout (0.5% chance)
        if random.random() < self.failure_rate * 0.5:
            raise TaskProviderTimeoutError("Request timeout")

    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        """
        List tasks with pagination.

        Simulates paginated API response like Azure DevOps.
        """
        await self._simulate_api_latency()

        total = len(self._tasks)
        start = (page - 1) * page_size
        end = start + page_size
        items = self._tasks[start:end]

        return TaskPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total,
        )

    async def get_task(self, external_id: str) -> ExternalTask | None:
        """Get a single task by external ID."""
        await self._simulate_api_latency()

        for task in self._tasks:
            if task.external_id == external_id:
                return task
        return None

    async def sync_tasks(self) -> list[ExternalTask]:
        """
        Fetch all tasks for import.

        Handles pagination internally and returns all tasks.
        """
        await self._simulate_api_latency()
        return self._tasks.copy()

    async def create_task(self, task: ExternalTaskCreate) -> ExternalTask:
        """
        Create a task in the mock system (push).

        Note: instances are short-lived (one per request/task), so the appended
        task won't persist across calls. That's fine — the caller persists the
        returned external_id on our own Task row.
        """
        await self._simulate_api_latency()

        external = ExternalTask(
            external_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            status=task.status,
            priority=task.priority,
            assignee_name=task.assignee_name,
            story_points=task.story_points,
        )
        self._tasks.append(external)
        return external

    async def update_task(
        self, external_id: str, changes: ExternalTaskUpdate
    ) -> ExternalTask:
        """Update a task in the mock system (push)."""
        await self._simulate_api_latency()

        for idx, existing in enumerate(self._tasks):
            if existing.external_id == external_id:
                updated = existing.model_copy(
                    update=changes.model_dump(exclude_none=True)
                )
                self._tasks[idx] = updated
                return updated

        # Not present in this short-lived instance — return the would-be result
        # so push stays non-fatal in the demo.
        return ExternalTask(
            external_id=external_id,
            title=changes.title or "(unknown)",
            description=changes.description,
            acceptance_criteria=changes.acceptance_criteria,
            status=changes.status or "backlog",
            priority=changes.priority or "medium",
            assignee_name=changes.assignee_name,
            story_points=changes.story_points,
        )
