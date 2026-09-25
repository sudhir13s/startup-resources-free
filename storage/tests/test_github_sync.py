"""GitHubDataSync — httpx.MockTransport covers pull/push without live API calls.

Uses `asyncio.run(...)` inside plain sync test functions (matches the
`agents/tests/*` convention) rather than pytest-asyncio, which is not a
declared project dependency.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from storage.github_sync import DataSyncError, GitHubDataSync

REPO_SLUG = "acme/repo"


def _sync(handler) -> GitHubDataSync:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
    return GitHubDataSync(repo_slug=REPO_SLUG, token="test-token", client=client)


def test_should_pull_file_when_it_exists(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ref"] == "data"
        return httpx.Response(200, content=b"db-bytes")

    sync = _sync(handler)
    dest = tmp_path / "resourceos.db"

    async def go():
        ok = await sync.pull(dest)
        await sync.aclose()
        return ok

    assert asyncio.run(go()) is True
    assert dest.read_bytes() == b"db-bytes"


def test_should_return_false_when_file_missing(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    sync = _sync(handler)

    async def go():
        ok = await sync.pull(tmp_path / "resourceos.db")
        await sync.aclose()
        return ok

    assert asyncio.run(go()) is False


def test_should_write_pulled_file_atomically(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"content")

    sync = _sync(handler)
    dest = tmp_path / "resourceos.db"

    async def go():
        await sync.pull(dest)
        await sync.aclose()

    asyncio.run(go())
    leftovers = [p for p in tmp_path.iterdir() if p != dest]
    assert leftovers == []


def test_should_push_to_existing_branch(tmp_path):
    src = tmp_path / "src.db"
    src.write_bytes(b"source-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == f"/repos/{REPO_SLUG}/git/blobs":
            return httpx.Response(201, json={"sha": "blobsha"})
        if path == f"/repos/{REPO_SLUG}/git/refs/heads/data" and method == "GET":
            return httpx.Response(200, json={"object": {"sha": "oldcommit"}})
        if path == f"/repos/{REPO_SLUG}/git/commits/oldcommit":
            return httpx.Response(200, json={"tree": {"sha": "oldtree"}})
        if path == f"/repos/{REPO_SLUG}/git/trees":
            assert b"oldtree" in request.content
            return httpx.Response(201, json={"sha": "newtree"})
        if path == f"/repos/{REPO_SLUG}/git/commits" and method == "POST":
            return httpx.Response(201, json={"sha": "newcommit"})
        if path == f"/repos/{REPO_SLUG}/git/refs/heads/data" and method == "PATCH":
            assert b'"force":false' in request.content
            return httpx.Response(200, json={"ref": "refs/heads/data"})
        raise AssertionError(f"unexpected {method} {path}")

    sync = _sync(handler)

    async def go():
        sha = await sync.push(src, "update db")
        await sync.aclose()
        return sha

    assert asyncio.run(go()) == "newcommit"


def test_should_push_creating_orphan_branch_when_missing(tmp_path):
    src = tmp_path / "src.db"
    src.write_bytes(b"source-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == f"/repos/{REPO_SLUG}/git/blobs":
            return httpx.Response(201, json={"sha": "blobsha"})
        if path == f"/repos/{REPO_SLUG}/git/refs/heads/data" and method == "GET":
            return httpx.Response(404, json={"message": "Not Found"})
        if path == f"/repos/{REPO_SLUG}/git/trees":
            assert b"base_tree" not in request.content
            return httpx.Response(201, json={"sha": "roottree"})
        if path == f"/repos/{REPO_SLUG}/git/commits" and method == "POST":
            assert b'"parents":[]' in request.content
            return httpx.Response(201, json={"sha": "rootcommit"})
        if path == f"/repos/{REPO_SLUG}/git/refs" and method == "POST":
            return httpx.Response(201, json={"ref": "refs/heads/data"})
        raise AssertionError(f"unexpected {method} {path}")

    sync = _sync(handler)

    async def go():
        sha = await sync.push(src, "initial commit")
        await sync.aclose()
        return sha

    assert asyncio.run(go()) == "rootcommit"


def test_should_retry_on_502_then_succeed(tmp_path):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(502)
        return httpx.Response(200, content=b"ok")

    sync = _sync(handler)

    async def go():
        ok = await sync.pull(tmp_path / "resourceos.db")
        await sync.aclose()
        return ok

    assert asyncio.run(go()) is True
    assert len(attempts) == 3


def test_should_raise_after_max_retries_exhausted(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    sync = _sync(handler)

    async def go():
        try:
            await sync.pull(tmp_path / "resourceos.db")
        finally:
            await sync.aclose()

    with pytest.raises(DataSyncError):
        asyncio.run(go())


def test_should_raise_on_non_retryable_non_404_status(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"})

    sync = _sync(handler)

    async def go():
        try:
            await sync.pull(tmp_path / "resourceos.db")
        finally:
            await sync.aclose()

    with pytest.raises(DataSyncError) as exc_info:
        asyncio.run(go())
    assert exc_info.value.status_code == 403


def test_should_retry_on_transport_error_then_succeed(tmp_path):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, content=b"ok")

    sync = _sync(handler)

    async def go():
        ok = await sync.pull(tmp_path / "resourceos.db")
        await sync.aclose()
        return ok

    assert asyncio.run(go()) is True
    assert len(attempts) == 2


def test_should_not_leave_temp_file_when_write_fails(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"content")

    sync = _sync(handler)
    dest = tmp_path / "readonly" / "resourceos.db"
    dest.parent.mkdir()

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("os.fdopen", _boom)

    async def go():
        try:
            await sync.pull(dest)
        finally:
            await sync.aclose()

    with pytest.raises(OSError):
        asyncio.run(go())
    assert list(dest.parent.iterdir()) == []


def test_should_not_retry_on_4xx(tmp_path):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(422, json={"message": "invalid"})

    sync = _sync(handler)

    async def go():
        try:
            await sync.push(Path(__file__), "bad push")
        finally:
            await sync.aclose()

    with pytest.raises(DataSyncError) as exc_info:
        asyncio.run(go())
    assert exc_info.value.status_code == 422
    assert len(attempts) == 1


def test_should_return_none_from_env_when_token_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_DATA_TOKEN", raising=False)
    assert GitHubDataSync.from_env() is None


def test_should_build_from_env_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_DATA_TOKEN", "secret-token")
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    monkeypatch.delenv("DATA_BRANCH", raising=False)
    sync = GitHubDataSync.from_env()
    assert sync is not None
    assert sync.repo_slug == "sudhir13s/startup-resources-free"
    assert sync.branch == "data"
