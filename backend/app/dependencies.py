"""Shared FastAPI dependencies."""

from app.database import get_db
from app.integrations.factory import get_task_provider

# Re-export shared dependencies for convenient imports
__all__ = ["get_db", "get_task_provider"]
