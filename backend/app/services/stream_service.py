"""Stream service: thin reads over streams + their sprints (keeps endpoints thin)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sprint import Sprint
from app.models.stream import Stream
from app.models.team import TeamMember


class StreamService:
    """Read-side helpers for streams and their in-flight sprints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_streams(self) -> list[Stream]:
        result = await self.db.execute(select(Stream).order_by(Stream.name))
        return list(result.scalars().all())

    async def get_stream(self, stream_id: str) -> Stream | None:
        result = await self.db.execute(
            select(Stream).where(Stream.id == stream_id)
        )
        return result.scalar_one_or_none()

    async def get_stream_sprints(
        self,
        stream_id: str,
        statuses: tuple[str, ...] = ("active", "planning"),
    ) -> list[Sprint]:
        result = await self.db.execute(
            select(Sprint)
            .where(Sprint.stream_id == stream_id, Sprint.status.in_(statuses))
            .order_by(Sprint.start_date)
        )
        return list(result.scalars().all())

    async def owner_names(self) -> dict[str, str]:
        """Map team_member id -> name, for resolving stream owners."""
        result = await self.db.execute(select(TeamMember.id, TeamMember.name))
        return {row[0]: row[1] for row in result.all()}
