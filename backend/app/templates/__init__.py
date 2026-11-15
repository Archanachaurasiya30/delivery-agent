"""Repo-seeding templates.

``sample_app/`` is a small, self-contained FastAPI Todo API used to seed demo
repositories so the coding agent has a real codebase to open PRs against. The
files here are DATA, not backend code: nothing in the backend imports them —
they are read as text and pushed to Azure Repos by ``RepoService``.
"""

from pathlib import Path


def load_sample_app() -> list[tuple[str, str]]:
    """All sample-app files as (repo-relative posix path, text content) pairs."""
    root = Path(__file__).resolve().parent / "sample_app"
    files: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        files.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
    return files
