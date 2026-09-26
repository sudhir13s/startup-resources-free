"""Sync the SQLite catalog DB to/from a Cloudflare R2 bucket (S3-compatible).

Render's free disk is ephemeral (architecture-v2 plan, Key decision 1): the
API pulls `resourceos.db` from the R2 bucket on boot, and pushes it back
after each refresh via a plain signed PUT, so history lives in object
storage rather than on the instance's disk.

R2 speaks the S3 API, so requests are signed with AWS Signature Version 4
(`storage/sigv4.py`) against the account's S3 endpoint, path-style:
`{endpoint}/{bucket}/{object_key}` where endpoint is what the R2 dashboard
shows (`https://<account-id>.r2.cloudflarestorage.com`, or a jurisdiction
variant such as `.eu.`), region `auto`, service `s3`. No `boto3`/`botocore` dependency — the API
runs on a 512 MB Render instance.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from storage.sigv4 import encode_uri_path, sign_request

logger = logging.getLogger(__name__)

_TIMEOUT_S = 30.0
_MAX_RETRIES = 3
_RETRYABLE_STATUS = {500, 502, 503, 504}
_REGION = "auto"
_SERVICE = "s3"
_DEFAULT_OBJECT_KEY = "resourceos.db"

_ENV_ENDPOINT = "RESOURCEOS_R2_ENDPOINT"
_ENV_BUCKET = "RESOURCEOS_R2_BUCKET"
_ENV_ACCESS_KEY_ID = "CF_USER_ACCESS_KEY_ID_19S"
_ENV_SECRET_ACCESS_KEY = "CF_USER_R2_SECRET_ACCESS_KEY_19S"
_ENV_OBJECT_KEY = "RESOURCEOS_R2_OBJECT_KEY"


class DataSyncError(RuntimeError):
    """Raised on any unrecoverable pull/push failure, carrying context for logs."""

    def __init__(self, message: str, *, status_code: int | None = None, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.context = context or {}


@dataclass
class R2DataSync:
    """Pulls/pushes one object (`resourceos.db` by default) in an R2 bucket."""

    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    object_key: str = _DEFAULT_OBJECT_KEY
    client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("R2 endpoint must be an https URL, e.g. https://<account-id>.r2.cloudflarestorage.com")
        self.endpoint = f"https://{parsed.netloc}"
        if self.client is None:
            self.client = httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT_S)

    @property
    def _base_url(self) -> str:
        return self.endpoint

    @property
    def _host(self) -> str:
        return urlparse(self.endpoint).netloc

    @property
    def _canonical_uri(self) -> str:
        return encode_uri_path(f"/{self.bucket}/{self.object_key}")

    @classmethod
    def from_env(cls) -> R2DataSync | None:
        """Build from RESOURCEOS_R2_ENDPOINT, RESOURCEOS_R2_BUCKET, CF_USER_ACCESS_KEY_ID_19S and CF_USER_R2_SECRET_ACCESS_KEY_19S; None unless all are set."""
        endpoint = os.environ.get(_ENV_ENDPOINT)
        bucket = os.environ.get(_ENV_BUCKET)
        access_key_id = os.environ.get(_ENV_ACCESS_KEY_ID)
        secret_access_key = os.environ.get(_ENV_SECRET_ACCESS_KEY)
        if not (endpoint and bucket and access_key_id and secret_access_key):
            return None
        object_key = os.environ.get(_ENV_OBJECT_KEY) or _DEFAULT_OBJECT_KEY
        return cls(
            endpoint=endpoint,
            bucket=bucket,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            object_key=object_key,
        )

    def _signed_headers(self, method: str, payload: bytes) -> dict[str, str]:
        result = sign_request(
            method=method,
            host=self._host,
            canonical_uri=self._canonical_uri,
            payload=payload,
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            region=_REGION,
            service=_SERVICE,
        )
        return {**result.headers, "host": self._host}

    async def _request(self, method: str, payload: bytes = b"") -> httpx.Response:
        """One signed HTTP call with retry on 5xx/network errors only (never on 4xx)."""
        assert self.client is not None
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            headers = self._signed_headers(method, payload)
            try:
                response = await self.client.request(
                    method, self._canonical_uri, content=payload or None, headers=headers
                )
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS:
                    return response
                last_error = DataSyncError(
                    f"{method} {self._canonical_uri} returned {response.status_code}",
                    status_code=response.status_code,
                )
            if attempt < _MAX_RETRIES - 1:
                backoff = (2**attempt) + random.uniform(0, 0.5)
                logger.warning("r2_sync_retry", extra={"attempt": attempt, "method": method})
                await self._sleep(backoff)
        raise DataSyncError(
            f"{method} {self._canonical_uri} failed after {_MAX_RETRIES} attempts",
            context={"cause": str(last_error)},
        )

    @staticmethod
    async def _sleep(seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def pull(self, dest: Path) -> bool:
        """Download the object into `dest`. False if the object doesn't exist."""
        response = await self._request("GET")
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
        """Upload `src` to the object key. `message` is logged only (R2 objects
        carry no commit message); returns the response ETag."""
        payload = src.read_bytes()
        response = await self._request("PUT", payload)
        if response.status_code >= 300:
            raise DataSyncError(
                f"push failed: {response.status_code}",
                status_code=response.status_code,
                context={"body": response.text[:500]},
            )
        # "message" is a reserved LogRecord attribute name — use "push_message" instead.
        logger.info("r2_sync_pushed", extra={"push_message": message, "bytes": len(payload)})
        return response.headers.get("etag", "").strip('"')

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        assert self.client is not None
        await self.client.aclose()
