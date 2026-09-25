"""R2DataSync — httpx.MockTransport covers pull/push without live R2 calls.

Uses `asyncio.run(...)` inside plain sync test functions (matches the
`agents/tests/*` convention) rather than pytest-asyncio, which is not a
declared project dependency.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import pytest

from storage.r2_sync import DataSyncError, R2DataSync

ACCOUNT_ID = "test-account-id"
BUCKET = "resourceos-data-test"
ACCESS_KEY_ID = "AKIDFAKEACCESSKEY"
SECRET_ACCESS_KEY = "fake/secret/access/key/never/real"  # noqa: S105 - obviously fake test fixture
OBJECT_KEY = "resourceos.db"
EXPECTED_PATH = f"/{BUCKET}/{OBJECT_KEY}"


def _sync(handler) -> R2DataSync:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    )
    return R2DataSync(
        account_id=ACCOUNT_ID,
        bucket=BUCKET,
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        object_key=OBJECT_KEY,
        client=client,
    )


def test_should_pull_file_when_it_exists(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == EXPECTED_PATH
        return httpx.Response(200, content=b"db-bytes")

    sync = _sync(handler)
    dest = tmp_path / "resourceos.db"

    async def go():
        ok = await sync.pull(dest)
        await sync.aclose()
        return ok

    assert asyncio.run(go()) is True
    assert dest.read_bytes() == b"db-bytes"


def test_should_return_false_when_object_missing(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"<Error><Code>NoSuchKey</Code></Error>")

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


def test_should_push_with_signed_put_and_return_etag(tmp_path):
    src = tmp_path / "src.db"
    src.write_bytes(b"source-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == EXPECTED_PATH
        assert request.content == b"source-bytes"
        auth = request.headers["Authorization"]
        assert auth.startswith(
            f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY_ID}/"
        )
        assert "/auto/s3/aws4_request" in auth
        assert "x-amz-date" in request.headers
        assert "x-amz-content-sha256" in request.headers
        return httpx.Response(200, headers={"ETag": '"abc123etag"'})

    sync = _sync(handler)

    async def go():
        etag = await sync.push(src, "update db")
        await sync.aclose()
        return etag

    assert asyncio.run(go()) == "abc123etag"


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


def test_should_raise_on_403_forbidden(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"<Error><Code>AccessDenied</Code></Error>")

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
        return httpx.Response(422, content=b"invalid")

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


def test_should_return_none_from_env_when_any_var_missing(monkeypatch):
    monkeypatch.delenv("RESOURCEOS_R2_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("RESOURCEOS_R2_BUCKET", BUCKET)
    monkeypatch.setenv("RESOURCEOS_R2_ACCESS_KEY_ID", ACCESS_KEY_ID)
    monkeypatch.setenv("RESOURCEOS_R2_SECRET_ACCESS_KEY", SECRET_ACCESS_KEY)
    assert R2DataSync.from_env() is None


def test_should_build_from_env_when_all_vars_present(monkeypatch):
    monkeypatch.setenv("RESOURCEOS_R2_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("RESOURCEOS_R2_BUCKET", BUCKET)
    monkeypatch.setenv("RESOURCEOS_R2_ACCESS_KEY_ID", ACCESS_KEY_ID)
    monkeypatch.setenv("RESOURCEOS_R2_SECRET_ACCESS_KEY", SECRET_ACCESS_KEY)
    monkeypatch.delenv("RESOURCEOS_R2_OBJECT_KEY", raising=False)
    sync = R2DataSync.from_env()
    assert sync is not None
    assert sync.account_id == ACCOUNT_ID
    assert sync.bucket == BUCKET
    assert sync.object_key == "resourceos.db"


def test_should_use_custom_object_key_from_env_when_set(monkeypatch):
    monkeypatch.setenv("RESOURCEOS_R2_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("RESOURCEOS_R2_BUCKET", BUCKET)
    monkeypatch.setenv("RESOURCEOS_R2_ACCESS_KEY_ID", ACCESS_KEY_ID)
    monkeypatch.setenv("RESOURCEOS_R2_SECRET_ACCESS_KEY", SECRET_ACCESS_KEY)
    monkeypatch.setenv("RESOURCEOS_R2_OBJECT_KEY", "custom.db")
    sync = R2DataSync.from_env()
    assert sync is not None
    assert sync.object_key == "custom.db"


def test_should_never_log_secret_when_pushing(tmp_path, caplog):
    src = tmp_path / "src.db"
    src.write_bytes(b"source-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"ETag": '"etag1"'})

    sync = _sync(handler)

    async def go():
        await sync.push(src, "update db")
        await sync.aclose()

    with caplog.at_level(logging.DEBUG):
        asyncio.run(go())

    log_text = caplog.text
    assert SECRET_ACCESS_KEY not in log_text
    assert "Authorization" not in log_text
