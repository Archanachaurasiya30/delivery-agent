"""Factory for selecting the active TaskProvider based on configuration."""

from app.config import settings
from app.integrations.mock_task_provider import MockTaskProvider
from app.integrations.task_provider import TaskProvider


def get_task_provider() -> TaskProvider:
    """Return the configured TaskProvider.

    "tfs"  -> real Azure DevOps / TFS provider
    else   -> MockTaskProvider (demo default)

    Usable as a FastAPI dependency (Depends(get_task_provider)) and called
    directly inside Celery tasks.
    """
    if settings.integration_provider == "dump":
        # Offline replay of a real capture — same mapping, no network.
        from app.integrations.dump_task_provider import DumpTaskProvider

        return DumpTaskProvider(
            dump_dir=settings.tfs_dump_dir,
            area_path=settings.tfs_area_path,
            # No max_items: the capture is already bounded by --sprints when it
            # was taken. TFS_MAX_ITEMS exists to spare the live server.
            sync_types=(
                tuple(
                    t.strip() for t in settings.tfs_sync_types.split(",") if t.strip()
                )
                or None
            ),
        )

    if settings.integration_provider == "tfs":
        # Imported lazily so the mock demo never requires TFS config/deps.
        from app.integrations.tfs_task_provider import TFSTaskProvider

        return TFSTaskProvider(
            org_url=settings.tfs_url,
            project=settings.tfs_project,
            pat=settings.tfs_pat,
            work_item_type=settings.tfs_work_item_type,
            # PUSH_ENABLED is the single dial: off means the provider itself
            # refuses writes, so no code path can mutate the real instance.
            read_only=not settings.push_enabled,
            api_version=settings.tfs_api_version,
            area_path=settings.tfs_area_path,
            max_items=settings.tfs_max_items,
            sync_types=(
                tuple(
                    t.strip() for t in settings.tfs_sync_types.split(",") if t.strip()
                )
                or None
            ),
        )

    if settings.integration_provider == "github":
        # GitHub Issues provider — same contract, for repos that live on GitHub.
        from app.integrations.github_task_provider import GitHubTaskProvider

        return GitHubTaskProvider(
            repo=settings.github_repo,
            token=settings.github_token,
            read_only=not settings.push_enabled,
        )

    # No simulated failures by default so the demo is deterministic.
    return MockTaskProvider(task_count=20, failure_rate=0.0)
