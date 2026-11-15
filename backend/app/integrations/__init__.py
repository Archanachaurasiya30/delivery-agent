"""Pluggable integration layer for external systems."""

from app.integrations.mock_task_provider import MockTaskProvider
from app.integrations.task_provider import ExternalTask, TaskPage, TaskProvider

__all__ = [
    "TaskProvider",
    "ExternalTask",
    "TaskPage",
    "MockTaskProvider",
]
