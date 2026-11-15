"""Repository provisioning for the coding agent (Azure Repos).

Creates target repos on demand and seeds empty ones with the bundled sample
Todo API so the agent always has a real codebase to open PRs against. Pure
ADO plumbing — no run/task state lives here.
"""

import logging

from app.config import settings
from app.integrations.ado_git_client import AdoGitClient
from app.integrations.task_provider import ReadOnlyProviderError
from app.templates import load_sample_app

logger = logging.getLogger(__name__)

# oldObjectId for a ref that doesn't exist yet (creates the branch).
_NEW_BRANCH_OBJECT_ID = "0" * 40


class RepoService:
    def __init__(self) -> None:
        self.ado = AdoGitClient(
            settings.tfs_url,
            settings.azure_repo_project or settings.tfs_project,
            settings.tfs_pat,
        )
        self.default_branch = settings.azure_repo_default_branch or "main"

    async def list_ado_repositories(self) -> list[str]:
        """Repo names in the configured project; [] when ADO is unreachable
        or unconfigured (the dispatch form degrades to config/prior-run repos)."""
        try:
            repos = await self.ado.list_repositories()
            return [r["name"] for r in repos if r.get("name")]
        except Exception as exc:  # noqa: BLE001 - listing is best-effort
            logger.warning("Could not list ADO repositories: %s", exc)
            return []

    async def create_and_seed(
        self, name: str, seed: bool = True, force_seed: bool = False
    ) -> dict:
        """Ensure repo ``name`` exists and (optionally) seed the sample app.

        Seeding happens when the default branch is empty, or unconditionally
        with ``force_seed`` (re-pushing files as edits over the existing tree).
        """
        # This creates repos and pushes commits into the configured ADO project.
        # It uses AdoGitClient rather than the TaskProvider, so the provider's
        # own read-only guard does not cover it — gate it on the same dial.
        if not settings.push_enabled:
            raise ReadOnlyProviderError(
                f"create_repository blocked: read-only mode "
                f"(set PUSH_ENABLED=true to allow writes to {settings.tfs_url})"
            )

        repo = await self.ado.get_repository(name)
        created = False
        if repo is None:
            await self.ado.create_repository(name)
            created = True

        head = await self.ado.get_branch_head(name, self.default_branch)

        seeded = False
        if seed and (head is None or force_seed):
            files = load_sample_app()
            if head is None:
                # Empty repo: one commit of adds creates the default branch.
                await self.ado.push_files(
                    name, self.default_branch, _NEW_BRANCH_OBJECT_ID, files,
                    "Seed sample application",
                )
            else:
                # Re-seed over existing content: edit what exists, add the rest.
                # Scope the listing to the branch we push to — the repo's own
                # ADO default branch may differ from the configured one.
                existing = await self.ado.list_item_paths(name, branch=self.default_branch)
                change_types = {
                    p: ("edit" if p in existing else "add") for p, _ in files
                }
                await self.ado.push_files(
                    name, self.default_branch, head, files,
                    "Seed sample application", change_types,
                )
            seeded = True

        return {
            "name": name,
            "web_url": self.ado.repo_web_url(name),
            "created": created,
            "seeded": seeded,
        }
