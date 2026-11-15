"""Shared async session helper for Celery tasks and standalone processes.

Each Celery task (and the long-poll bot) runs its own event loop via
``asyncio.run``. asyncpg connections are bound to the loop that created them,
so we must NOT share the app-level engine/pool across these loops. Instead each
task creates its own short-lived engine + session. Low volume at demo scale; a
shared pooled session is a future optimisation.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def create_task_session() -> AsyncSession:
    """Create a fresh AsyncSession (and engine) for a single task/loop.

    IMPORTANT: Each Celery task / async entrypoint must create its own session
    and never share it across tasks or event loops.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        # No pool: the engine is never disposed (it dies with the task's event
        # loop), so a pool leaked its idle connections on every task until
        # Postgres hit max_connections ("too many clients already"). NullPool
        # closes the connection when the session closes.
        poolclass=NullPool,
    )
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return session_maker()
