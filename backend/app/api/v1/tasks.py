"""Task management API endpoints."""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.integrations.mock_task_provider import MockTaskProvider
from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskSummary,
    TaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _enqueue_push(task_id: str, op: str) -> None:
    """Queue a background push of a task to the external provider.

    Imported lazily so the API module never hard-depends on the Celery task
    module at import time. The task itself guards on push_enabled / task.source.
    """
    if not settings.push_enabled:
        return
    from app.tasks.tfs_tasks import push_task_to_provider

    push_task_to_provider.delay(task_id, op)


class ImportMockResponse(BaseModel):
    """Response schema for mock import endpoint."""

    imported: int
    tasks: list[TaskResponse]


class SyncResponse(BaseModel):
    """Response schema for the provider sync endpoint."""

    provider: str
    inserted: int
    updated: int


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """
    List all tasks with pagination and optional filters.

    Args:
        skip: Number of records to skip (default 0)
        limit: Maximum number of records to return (default 50)
        status: Filter by status (backlog, todo, in_progress, review, done)
        priority: Filter by priority (low, medium, high, critical)
        assignee_id: Filter by assigned team member
        db: Database session

    Returns:
        List of tasks with total count
    """
    service = TaskService(db)
    tasks, total = await service.list_tasks(
        skip=skip,
        limit=limit,
        status_filter=status,
        priority_filter=priority,
        assignee_id=assignee_id,
    )
    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """
    Create a new task.

    Args:
        data: Task creation data
        db: Database session

    Returns:
        Created task

    Raises:
        404: If assignee_id provided but team member not found
        422: If validation fails
    """
    service = TaskService(db)
    task = await service.create_task(data)
    # Commit so the row is visible to the worker, then push to the provider.
    await db.commit()
    await db.refresh(task)
    _enqueue_push(str(task.id), "create")
    return TaskResponse.model_validate(task)


@router.get("/summary", response_model=TaskSummary)
async def get_task_summary(
    db: AsyncSession = Depends(get_db),
) -> TaskSummary:
    """
    Get task summary with counts by status and priority.

    Args:
        db: Database session

    Returns:
        Summary with total count, counts by status, and counts by priority
    """
    service = TaskService(db)
    summary = await service.get_summary()
    return TaskSummary(**summary)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """
    Get a task by ID.

    Args:
        task_id: UUID of the task
        db: Database session

    Returns:
        Task details

    Raises:
        404: If task not found
    """
    service = TaskService(db)
    task = await service.get_task(task_id)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """
    Update a task with partial data.

    Args:
        task_id: UUID of the task
        data: Partial update data
        db: Database session

    Returns:
        Updated task

    Raises:
        404: If task or assignee not found
        422: If validation fails
    """
    service = TaskService(db)
    task = await service.update_task(task_id, data)
    await db.commit()
    await db.refresh(task)
    _enqueue_push(str(task.id), "update")
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a task.

    Args:
        task_id: UUID of the task
        db: Database session

    Raises:
        404: If task not found
    """
    service = TaskService(db)
    await service.delete_task(task_id)


@router.post("/sync", response_model=SyncResponse)
async def sync_tasks_from_provider(
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """
    Pull work items from the configured provider (mock or TFS) into our DB.

    Synchronous so the UI gets immediate counts and can refresh the board.
    Upserts on external_id — running it repeatedly updates, not duplicates.
    """
    from app.integrations.factory import get_task_provider
    from app.integrations.task_provider import RateLimitError, TaskProviderTimeoutError

    service = TaskService(db)
    provider = get_task_provider()
    try:
        result = await service.import_from_provider(
            provider, source_label=settings.integration_provider
        )
    except TaskProviderTimeoutError as exc:
        # On-prem TFS is reachable on the corporate network only, so "off VPN"
        # is the common case. A clear 503 beats an opaque 500 stack trace.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{settings.tfs_url} did not respond ({exc}). "
                "Check you are on the corporate network / VPN."
            ),
        )
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Provider rate limit: {exc}",
            headers={"Retry-After": str(exc.retry_after)},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach {settings.tfs_url}: {exc}",
        )
    await db.commit()
    return SyncResponse(
        provider=settings.integration_provider,
        inserted=len(result["inserted"]),
        updated=len(result["updated"]),
    )


@router.post("/import-mock", response_model=ImportMockResponse)
async def import_mock_tasks(
    db: AsyncSession = Depends(get_db),
) -> ImportMockResponse:
    """
    Import sample tasks from mock provider.

    Creates 15-20 realistic sample tasks for development/testing.
    Uses external_id to deduplicate - importing twice doesn't create duplicates.

    Args:
        db: Database session

    Returns:
        Number of imported tasks and their details
    """
    service = TaskService(db)
    provider = MockTaskProvider(task_count=20, failure_rate=0.0)  # No failures for import
    result = await service.import_from_provider(provider, source_label="mock")
    imported_tasks = result["inserted"]

    return ImportMockResponse(
        imported=len(imported_tasks),
        tasks=[TaskResponse.model_validate(t) for t in imported_tasks],
    )
