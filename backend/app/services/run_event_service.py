"""Append-only progress events for coding-agent runs.

``RunEventRecorder`` is the write side of the run timeline: agents call
``emit()`` as they work and the API reads the rows back for the UI. Each emit
opens its OWN short-lived session (via ``create_task_session``) and commits
immediately, so events become visible to API readers while the caller's
long-running task transaction is still open.

Telemetry must never fail a run: ``emit()`` swallows every exception and logs
a warning instead.
"""

import logging
from typing import Awaitable, Callable

from sqlalchemy import func, select

from app.models.agent_run_event import AgentRunEvent
from app.tasks.db import create_task_session

logger = logging.getLogger(__name__)

# Callback shape agents accept so they can emit events without knowing about
# the DB: (kind, message, payload) -> awaitable. RunEventRecorder.emit fits it.
EventSink = Callable[[str, str, dict | None], Awaitable[None]]

# Keep messages readable in the UI; payload carries the full detail.
_MAX_MESSAGE_LEN = 500


class RunEventRecorder:
    """Emits ordered AgentRunEvents for one run, one commit per event."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        # Lazily initialised from MAX(seq) on first emit, then kept in memory
        # (only one recorder writes a given run at a time).
        self._seq: int | None = None

    async def emit(self, kind: str, message: str, payload: dict | None = None) -> None:
        try:
            async with create_task_session() as session:
                if self._seq is None:
                    res = await session.execute(
                        select(func.max(AgentRunEvent.seq)).where(
                            AgentRunEvent.run_id == self.run_id
                        )
                    )
                    self._seq = res.scalar() or 0
                self._seq += 1
                session.add(
                    AgentRunEvent(
                        run_id=self.run_id,
                        seq=self._seq,
                        kind=kind,
                        message=message[:_MAX_MESSAGE_LEN],
                        payload=payload,
                    )
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - telemetry must not fail a run
            logger.warning(
                "run-event emit failed (run=%s, kind=%s): %s", self.run_id, kind, exc
            )
