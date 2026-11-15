"""Factory for selecting the active CodingAgent based on configuration.

Structural clone of ``factory.get_task_provider`` — the ONLY thing dispatch
callers import, so swapping mock <-> azure_devops is a config change with no
caller change (acceptance criterion E).
"""

from app.config import settings
from app.integrations.coding_agent import CodingAgent
from app.integrations.mock_coding_agent import MockCodingAgent


def get_coding_agent() -> CodingAgent:
    """Return the configured CodingAgent.

    "azure_devops" -> real Azure Repos PRs + Azure Pipelines CI
    "claude_code"  -> headless Claude Code CLI in a git workspace (ADO PRs/CI)
    else           -> MockCodingAgent (deterministic local default)
    """
    if settings.coding_agent_provider == "azure_devops":
        # Imported lazily so the mock demo never requires Azure config/deps.
        from app.integrations.azure_devops_coding_agent import AzureDevOpsCodingAgent

        return AzureDevOpsCodingAgent(
            org_url=settings.tfs_url,
            project=settings.azure_repo_project,
            repo_id=settings.azure_repo_id,
            pat=settings.tfs_pat,
            default_branch=settings.azure_repo_default_branch,
            pipeline_id=settings.azure_pipeline_id,
        )

    if settings.coding_agent_provider == "claude_code":
        # Imported lazily so non-claude deployments never need the CLI/token.
        from app.integrations.claude_code_coding_agent import ClaudeCodeCodingAgent

        return ClaudeCodeCodingAgent(
            org_url=settings.tfs_url,
            project=settings.azure_repo_project or settings.tfs_project,
            default_repo=settings.azure_repo_id,
            pat=settings.tfs_pat,
            default_branch=settings.azure_repo_default_branch,
            pipeline_id=settings.azure_pipeline_id,
            model=settings.claude_code_model,
            max_turns=settings.claude_code_max_turns,
            timeout_seconds=settings.claude_code_timeout_seconds,
            workspace_root=settings.claude_code_workspace_dir,
        )

    return MockCodingAgent()
