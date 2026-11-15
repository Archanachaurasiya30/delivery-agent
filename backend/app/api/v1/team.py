"""Team management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.team import (
    TeamMemberCreate,
    TeamMemberListResponse,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members", response_model=TeamMemberListResponse)
async def list_team_members(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> TeamMemberListResponse:
    """
    List all team members with pagination.

    Args:
        skip: Number of records to skip (default 0)
        limit: Maximum number of records to return (default 50)
        db: Database session

    Returns:
        List of team members with total count
    """
    service = TeamService(db)
    members, total = await service.list_members(skip=skip, limit=limit)
    return TeamMemberListResponse(
        members=[TeamMemberResponse.model_validate(m) for m in members],
        total=total,
    )


@router.post(
    "/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team_member(
    data: TeamMemberCreate,
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """
    Create a new team member.

    Args:
        data: Team member creation data
        db: Database session

    Returns:
        Created team member

    Raises:
        409: If email already exists
        422: If validation fails
    """
    service = TeamService(db)
    member = await service.create_member(data)
    return TeamMemberResponse.model_validate(member)


@router.get("/members/{member_id}", response_model=TeamMemberResponse)
async def get_team_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """
    Get a team member by ID.

    Args:
        member_id: UUID of the team member
        db: Database session

    Returns:
        Team member details

    Raises:
        404: If member not found
    """
    service = TeamService(db)
    member = await service.get_member(member_id)
    return TeamMemberResponse.model_validate(member)


@router.patch("/members/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: UUID,
    data: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """
    Update a team member with partial data.

    Args:
        member_id: UUID of the team member
        data: Partial update data
        db: Database session

    Returns:
        Updated team member

    Raises:
        404: If member not found
        409: If email already exists
        422: If validation fails
    """
    service = TeamService(db)
    member = await service.update_member(member_id, data)
    return TeamMemberResponse.model_validate(member)


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_team_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a team member.

    Args:
        member_id: UUID of the team member
        db: Database session

    Raises:
        404: If member not found
    """
    service = TeamService(db)
    await service.delete_member(member_id)


@router.post(
    "/members/{member_id}/toggle-availability",
    response_model=TeamMemberResponse,
)
async def toggle_team_member_availability(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """
    Toggle a team member's availability status.

    Args:
        member_id: UUID of the team member
        db: Database session

    Returns:
        Updated team member with toggled availability

    Raises:
        404: If member not found
    """
    service = TeamService(db)
    member = await service.toggle_availability(member_id)
    return TeamMemberResponse.model_validate(member)
