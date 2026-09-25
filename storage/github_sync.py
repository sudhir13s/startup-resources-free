"""Sync the SQLite catalog DB to/from a dedicated `data` branch via the GitHub API.

Render's free disk is ephemeral (architecture-v2 plan, Key decision 1): the
API pulls `resourceos.db` from the `data` branch on boot, and pushes it back
after each refresh via the Git Data API (blob -> tree -> commit -> ref), so
history lives in git rather than on the instance's disk.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_ROOT = "https://api.github.com"
_TIMEOUT_S = 30.0
_MAX_RETRIES = 3
_RETRYABLE_STATUS = {500, 502, 503, 504}


class DataSyncError(RuntimeError):
    """Raised on any unrecoverable pull/push failure, carrying context for logs."""

    def __init__(self, message: str, *, status_code: int | None = None, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.context = context or {}


@dataclass
class GitHubDataSync:
    """Pulls/pushes one file (`resourceos.db` by default) on a `data` branch."""

    repo_slug: str
    token: str
    branch: str = "data"
    file_path: str = "resourceos.db"
    client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=_API_ROOT,
                timeout=_TIMEOUT_S,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

    @classmethod
    def from_env(cls) -> GitHubDataSync | None:
        """Build from `RESOURCEOS_GITHUB_TOKEN`/`RESOURCEOS_DATA_REPO`/`RESOURCEOS_DATA_BRANCH`; None when the token is missing."""
        token = os.environ.get("RESOURCEOS_GITHUB_TOKEN")
        if not token:
            return None
        repo_slug = os.environ.get("RESOURCEOS_DATA_REPO", "sudhir13s/startup-resources-free")
        branch = os.environ.get("RESOURCEOS_DATA_BRANCH", "data")
        return cls(repo_slug=repo_slug, token=token, branch=branch)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One HTTP call with retry on 5xx/network errors only (never on 4xx)."""
        assert self.client is not None
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self.client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS:
                    return response
                last_error = DataSyncError(
                    f"{method} {url} returned {response.status_code}",
                    status_code=response.status_code,
                )
            if attempt < _MAX_RETRIES - 1:
                backoff = (2**attempt) + random.uniform(0, 0.5)
                logger.warning("github_sync_retry", extra={"attempt": attempt, "url": url})
                await self._sleep(backoff)
        raise DataSyncError(f"{method} {url} failed after {_MAX_RETRIES} attempts", context={"cause": str(last_error)})

    @staticmethod
    async def _sleep(seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def pull(self, dest: Path) -> bool:
        """Download the file from the data branch into `dest`. False if branch/file missing."""
        assert self.client is not None
        url = f"/repos/{self.repo_slug}/contents/{self.file_path}"
        response = await self._request(
            "GET",
            url,
            params={"ref": self.branch},
            headers={"Accept": "application/vnd.github.raw"},
        )
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise DataSyncError(
                f"pull failed: {response.status_code}",
                status_code=response.status_code,
                context={"body": response.text[:500]},
            )
        self._atomic_write(dest, response.content)
        return True

    @staticmethod
    def _atomic_write(dest: Path, content: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            tmp_path.replace(dest)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    async def push(self, src: Path, message: str) -> str:
        """Commit `src` to the data branch via the Git Data API. Returns the new commit sha."""
        blob_sha = await self._create_blob(src)
        base_commit_sha, base_tree_sha = await self._get_branch_head()
        parents = [base_commit_sha] if base_commit_sha else []
        tree_sha = await self._create_tree(blob_sha, base_tree_sha)
        commit_sha = await self._create_commit(message, tree_sha, parents)
        await self._update_ref(commit_sha, create=base_commit_sha is None)
        return commit_sha

    async def _create_blob(self, src: Path) -> str:
        content_b64 = base64.b64encode(src.read_bytes()).decode("ascii")
        response = await self._request(
            "POST",
            f"/repos/{self.repo_slug}/git/blobs",
            json={"content": content_b64, "encoding": "base64"},
        )
        self._raise_for_status(response, "create blob")
        return response.json()["sha"]

    async def _get_branch_head(self) -> tuple[str | None, str | None]:
        """Current (commit_sha, tree_sha) for the branch, or (None, None) when it doesn't exist yet."""
        response = await self._request("GET", f"/repos/{self.repo_slug}/git/refs/heads/{self.branch}")
        if response.status_code == 404:
            return None, None
        self._raise_for_status(response, "get ref")
        commit_sha = response.json()["object"]["sha"]
        commit_response = await self._request("GET", f"/repos/{self.repo_slug}/git/commits/{commit_sha}")
        self._raise_for_status(commit_response, "get commit")
        return commit_sha, commit_response.json()["tree"]["sha"]

    async def _create_tree(self, blob_sha: str, base_tree_sha: str | None) -> str:
        """New tree with this file's blob. An orphan push uses a tree with only this file."""
        payload: dict[str, Any] = {
            "tree": [{"path": self.file_path, "mode": "100644", "type": "blob", "sha": blob_sha}]
        }
        if base_tree_sha is not None:
            payload["base_tree"] = base_tree_sha
        response = await self._request("POST", f"/repos/{self.repo_slug}/git/trees", json=payload)
        self._raise_for_status(response, "create tree")
        return response.json()["sha"]

    async def _create_commit(self, message: str, tree_sha: str, parents: list[str]) -> str:
        response = await self._request(
            "POST",
            f"/repos/{self.repo_slug}/git/commits",
            json={"message": message, "tree": tree_sha, "parents": parents},
        )
        self._raise_for_status(response, "create commit")
        return response.json()["sha"]

    async def _update_ref(self, commit_sha: str, *, create: bool) -> None:
        """Point the branch ref at the new commit; create it (orphan) if it didn't exist."""
        if create:
            response = await self._request(
                "POST",
                f"/repos/{self.repo_slug}/git/refs",
                json={"ref": f"refs/heads/{self.branch}", "sha": commit_sha},
            )
        else:
            response = await self._request(
                "PATCH",
                f"/repos/{self.repo_slug}/git/refs/heads/{self.branch}",
                json={"sha": commit_sha, "force": False},
            )
        self._raise_for_status(response, "update ref")

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        if response.status_code >= 300:
            raise DataSyncError(
                f"{action} failed: {response.status_code}",
                status_code=response.status_code,
                context={"body": response.text[:500]},
            )

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        assert self.client is not None
        await self.client.aclose()
