"""One typed `Settings` object, built from env once at startup, fail fast.

No scattered `os.environ` reads elsewhere in `api/` — every other module
takes a `Settings` instance (or reads it off `app.state`).
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, SecretStr

from storage.r2_sync import R2DataSync

DEFAULT_DB_PATH = "data/resourceos.db"
DEFAULT_SEED_PATH = "data/providers_seed.json"
DEFAULT_R2_OBJECT_KEY = "resourceos.db"


class Settings(BaseModel):
    """Validated application configuration, resolved once at process start."""

    # SecretStr: the password never appears in a repr, log line, or
    # traceback — only `.get_secret_value()` (in api/deps.py, request-signing
    # only) reads the raw value.
    password: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    db_path: str = DEFAULT_DB_PATH
    seed_path: str = DEFAULT_SEED_PATH
    r2_endpoint: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_object_key: str = DEFAULT_R2_OBJECT_KEY

    def build_sync(self) -> R2DataSync | None:
        """Construct the R2 sync client, or None when any credential is missing."""
        if not (self.r2_endpoint and self.r2_bucket and self.r2_access_key_id and self.r2_secret_access_key):
            return None
        return R2DataSync(
            endpoint=self.r2_endpoint,
            bucket=self.r2_bucket,
            access_key_id=self.r2_access_key_id,
            secret_access_key=self.r2_secret_access_key,
            object_key=self.r2_object_key,
        )


def _resolve_cors_origins() -> list[str]:
    """Resolve the CORS allow-list from `CORS_ORIGINS` (comma-separated full
    URLs) or `CORS_ORIGIN_HOST` (Render `fromService.host` — a bare
    hostname, scheme added). Falls back to an empty allow-list when neither
    is set: the browser never calls this API directly (only the Next.js
    server, which is not subject to CORS), so the safe default denies every
    browser origin. `CORS_ORIGINS` remains available as an explicit opt-in
    for local debugging against the API from a browser.

    A `CORS_ORIGIN_HOST` with no dot (a raw Render service name) gets
    `.onrender.com` appended so a `fromService` value still yields a
    matchable Origin header.
    """
    explicit = os.environ.get("CORS_ORIGINS", "").strip()
    if explicit:
        return [origin.strip() for origin in explicit.split(",") if origin.strip()]
    host = os.environ.get("CORS_ORIGIN_HOST", "").strip()
    if host:
        cleaned = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        full = cleaned if "." in cleaned else f"{cleaned}.onrender.com"
        return [f"https://{full}"]
    return []


def load_settings() -> Settings:
    """Build `Settings` from the process environment. Called once at startup."""
    raw_password = os.environ.get("RESOURCEOS_PASSWORD") or None
    return Settings(
        password=SecretStr(raw_password) if raw_password else None,
        cors_origins=_resolve_cors_origins(),
        db_path=os.environ.get("RESOURCEOS_DB_PATH", DEFAULT_DB_PATH),
        seed_path=os.environ.get("SEED_PATH", DEFAULT_SEED_PATH),
        r2_endpoint=os.environ.get("RESOURCEOS_R2_ENDPOINT") or None,
        r2_bucket=os.environ.get("RESOURCEOS_R2_BUCKET") or None,
        r2_access_key_id=os.environ.get("CF_USER_ACCESS_KEY_ID") or None,
        r2_secret_access_key=os.environ.get("CF_USER_R2_SECRET_ACCESS_KEY") or None,
        r2_object_key=os.environ.get("RESOURCEOS_R2_OBJECT_KEY", DEFAULT_R2_OBJECT_KEY),
    )
