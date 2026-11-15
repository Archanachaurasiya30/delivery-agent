"""Plain Azure DevOps Git/Build REST client (api-version 7.1).

A thin, agent-agnostic wrapper around the ADO REST endpoints the coding-agent
stack needs: repository CRUD, refs, pushes, items, pull requests, and builds.
Reuses the PAT -> ``base64(":"+pat)`` Basic auth + ``httpx.AsyncClient`` pattern
from ``AzureDevOpsCodingAgent`` and raises the same ``CodingAgentError`` on any
API failure, so callers get one error surface regardless of adapter.

Unlike ``AzureDevOpsCodingAgent`` this class has no LLM logic and no configured
default repo — every call takes the repo explicitly, which is what the
workspace-based (Claude Code) agent and the repo-seeding service need.
"""

import base64
import logging
from urllib.parse import quote

import httpx

from app.integrations.coding_agent import CodingAgentError

logger = logging.getLogger(__name__)

API_VERSION = "7.1"


class AdoGitClient:
    def __init__(self, org_url: str, project: str, pat: str, timeout: float = 60.0) -> None:
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.timeout = timeout
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._auth_header = f"Basic {token}"

    # ---- HTTP plumbing (mirrors AzureDevOpsCodingAgent) ----
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout, headers={"Authorization": self._auth_header}
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise CodingAgentError(
                f"Azure DevOps API error {resp.status_code}: {resp.text[:500]}"
            )

    def _repos_url(self, path: str = "") -> str:
        base = f"{self.org_url}/{self.project}/_apis/git/repositories"
        return f"{base}/{path}" if path else base

    def _git(self, repo: str, path: str) -> str:
        # Repo names may contain spaces etc. — encode the path segment.
        return self._repos_url(f"{quote(repo, safe='')}/{path}")

    # ---- URLs ----
    def clone_url(self, repo: str) -> str:
        return f"{self.org_url}/{self.project}/_git/{quote(repo, safe='')}"

    def repo_web_url(self, repo: str) -> str:
        # ADO's web view of a repo is the same URL as its HTTPS clone URL.
        return self.clone_url(repo)

    # ---- Repositories ----
    async def list_repositories(self) -> list[dict]:
        async with self._client() as client:
            resp = await client.get(f"{self._repos_url()}?api-version={API_VERSION}")
            self._raise_for_status(resp)
            return resp.json().get("value", [])

    async def get_repository(self, name: str) -> dict | None:
        async with self._client() as client:
            resp = await client.get(
                f"{self._repos_url(quote(name, safe=''))}?api-version={API_VERSION}"
            )
            if resp.status_code == 404:
                return None
            self._raise_for_status(resp)
            return resp.json()

    async def create_repository(self, name: str) -> dict:
        async with self._client() as client:
            resp = await client.post(
                f"{self._repos_url()}?api-version={API_VERSION}", json={"name": name}
            )
            self._raise_for_status(resp)
            return resp.json()

    # ---- Refs / pushes / items ----
    async def get_branch_head(self, repo: str, branch: str) -> str | None:
        """Object id of ``refs/heads/{branch}``, or None if absent / repo empty."""
        url = self._git(repo, f"refs?filter=heads/{branch}&api-version={API_VERSION}")
        async with self._client() as client:
            resp = await client.get(url)
            if resp.status_code == 404:  # brand-new empty repo
                return None
            self._raise_for_status(resp)
        # The filter is a prefix match ("heads/main" also matches
        # "heads/main-fix"), so pick the exact ref.
        for ref in resp.json().get("value", []):
            if ref.get("name") == f"refs/heads/{branch}":
                return ref["objectId"]
        return None

    async def push_files(
        self,
        repo: str,
        branch: str,
        old_object_id: str,
        files: list[tuple[str, str]],
        message: str,
        change_types: dict[str, str] | None = None,
    ) -> dict:
        """Push one commit with the given (path, content) files to ``branch``.

        ``old_object_id`` is the current branch head ("0"*40 creates the
        branch); ``change_types`` maps a path to "add"/"edit" (default "add").
        """
        change_types = change_types or {}
        body = {
            "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": old_object_id}],
            "commits": [{
                "comment": message,
                "changes": [
                    {
                        "changeType": change_types.get(path, "add"),
                        "item": {"path": "/" + path.lstrip("/")},
                        "newContent": {"content": content, "contentType": "rawtext"},
                    }
                    for path, content in files
                ],
            }],
        }
        async with self._client() as client:
            resp = await client.post(self._git(repo, f"pushes?api-version={API_VERSION}"), json=body)
            self._raise_for_status(resp)
            return resp.json()

    async def list_item_paths(self, repo: str, branch: str | None = None) -> set[str]:
        """All file paths in the repo (repo-relative, no leading "/").

        ``branch`` scopes the listing (defaults to the repo's own default
        branch when omitted). ADO returns 404 for an empty repository —
        treated as "no items".
        """
        version = (
            f"&versionDescriptor.version={quote(branch, safe='')}"
            "&versionDescriptor.versionType=branch"
            if branch
            else ""
        )
        url = self._git(repo, f"items?recursionLevel=Full{version}&api-version={API_VERSION}")
        async with self._client() as client:
            resp = await client.get(url)
            if resp.status_code == 404:  # empty repo
                return set()
            self._raise_for_status(resp)
        return {
            item["path"].lstrip("/")
            for item in resp.json().get("value", [])
            if not item.get("isFolder") and item.get("path")
        }

    # ---- Pull requests ----
    async def create_pr(
        self, repo: str, source_branch: str, target_branch: str, title: str, description: str
    ) -> tuple[str, str]:
        body = {
            "sourceRefName": f"refs/heads/{source_branch}",
            "targetRefName": f"refs/heads/{target_branch}",
            "title": title,
            "description": description,
        }
        async with self._client() as client:
            resp = await client.post(
                self._git(repo, f"pullrequests?api-version={API_VERSION}"), json=body
            )
            self._raise_for_status(resp)
        pr = resp.json()
        pr_id = str(pr["pullRequestId"])
        pr_url = f"{self.org_url}/{self.project}/_git/{repo}/pullrequest/{pr_id}"
        return pr_id, pr_url

    async def find_active_pr(self, repo: str, source_branch: str) -> tuple[str, str] | None:
        """(pr_id, pr_url) of the active PR from ``source_branch``, if any."""
        url = self._git(
            repo,
            f"pullrequests?searchCriteria.sourceRefName=refs/heads/{source_branch}"
            f"&searchCriteria.status=active&api-version={API_VERSION}",
        )
        async with self._client() as client:
            resp = await client.get(url)
            self._raise_for_status(resp)
        prs = resp.json().get("value", [])
        if not prs:
            return None
        pr_id = str(prs[0]["pullRequestId"])
        pr_url = f"{self.org_url}/{self.project}/_git/{repo}/pullrequest/{pr_id}"
        return pr_id, pr_url

    async def complete_pr(self, repo: str, pr_id: str) -> dict:
        """Complete (squash-merge) a PR — mirrors ``AzureDevOpsCodingAgent.merge``."""
        async with self._client() as client:
            # Fetch the PR for its last source commit (required to complete).
            get = await client.get(self._git(repo, f"pullrequests/{pr_id}?api-version={API_VERSION}"))
            self._raise_for_status(get)
            pr = get.json()
            body = {
                "status": "completed",
                "lastMergeSourceCommit": pr.get("lastMergeSourceCommit"),
                "completionOptions": {"mergeStrategy": "squash", "deleteSourceBranch": True},
            }
            patch = await client.patch(
                self._git(repo, f"pullrequests/{pr_id}?api-version={API_VERSION}"), json=body
            )
            self._raise_for_status(patch)
            return patch.json()

    # ---- Builds ----
    async def get_latest_build(self, pipeline_id: str, branch: str) -> dict | None:
        url = (
            f"{self.org_url}/{self.project}/_apis/build/builds"
            f"?definitions={pipeline_id}&branchName=refs/heads/{branch}"
            f"&$top=1&api-version={API_VERSION}"
        )
        async with self._client() as client:
            resp = await client.get(url)
            self._raise_for_status(resp)
        builds = resp.json().get("value", [])
        return builds[0] if builds else None
