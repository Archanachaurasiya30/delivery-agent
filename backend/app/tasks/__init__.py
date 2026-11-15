"""Celery task definitions and configuration.

This module provides background task processing via Celery with Redis broker.
"""

from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
