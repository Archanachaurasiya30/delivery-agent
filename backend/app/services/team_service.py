"""Team management service layer."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import TeamMember
from app.schemas.team import TeamMemberCreate, TeamMemberUpdate


class TeamService:
    """Service class for team member operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_members(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[TeamMember], int]:
        """
        List team members with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of team members, total count)
        """
        # Get total count
        count_query = select(func.count()).select_from(TeamMember)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated members
        query = select(TeamMember).offset(skip).limit(limit).order_by(TeamMember.name)
        result = await self.db.execute(query)
        members = list(result.scalars().all())

        return members, total

    async def get_member(self, member_id: UUID) -> TeamMember:
        """
        Get a team member by ID.

        Args:
            member_id: UUID of the team member

        Returns:
            TeamMember instance

        Raises:
            HTTPException: 404 if member not found
        """
        query = select(TeamMember).where(TeamMember.id == member_id)
        result = await self.db.execute(query)
        member = result.scalar_one_or_none()

        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team member with id {member_id} not found",
            )

        return member

    async def create_member(self, data: TeamMemberCreate) -> TeamMember:
        """
        Create a new team member.

        Args:
            data: Team member creation data

        Returns:
            Created TeamMember instance

        Raises:
            HTTPException: 409 if email already exists
        """
        member = TeamMember(**data.model_dump())
        self.db.add(member)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Team member with email {data.email} already exists",
            )

        return member

    async def update_member(
        self, member_id: UUID, data: TeamMemberUpdate
    ) -> TeamMember:
        """
        Update a team member with partial data.

        Args:
            member_id: UUID of the team member
            data: Partial update data

        Returns:
            Updated TeamMember instance

        Raises:
            HTTPException: 404 if member not found, 409 if email conflict
        """
        member = await self.get_member(member_id)

        # Apply only provided fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(member, field, value)

        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Team member with email {data.email} already exists",
            )

        return member

    async def delete_member(self, member_id: UUID) -> None:
        """
        Delete a team member.

        Args:
            member_id: UUID of the team member

        Raises:
            HTTPException: 404 if member not found
        """
        member = await self.get_member(member_id)
        await self.db.delete(member)
        await self.db.flush()

    async def toggle_availability(self, member_id: UUID) -> TeamMember:
        """
        Toggle a team member's availability status.

        Args:
            member_id: UUID of the team member

        Returns:
            Updated TeamMember instance

        Raises:
            HTTPException: 404 if member not found
        """
        member = await self.get_member(member_id)
        member.is_available = not member.is_available
        await self.db.flush()
        return member
