"""Shared FastAPI dependencies."""

import secrets

from app.config import settings
from app.database import get_db
from app.integrations.factory import get_task_provider

# Re-export shared dependencies for convenient imports
__all__ = ["get_db", "get_task_provider"]

# Cookie set by the /api/v1/passcode unlock page (issue #8).
PASSCODE_COOKIE = "da_passcode"


def passcode_ok(supplied: str | None) -> bool:
    """True when no gate is configured, or the supplied secret matches."""
    if not settings.passcode:
        return True
    # bytes form: compare_digest raises on non-ASCII str, never on bytes
    return bool(supplied) and secrets.compare_digest(
        supplied.encode(), settings.passcode.encode()
    )
