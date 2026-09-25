"""One typed `Settings` object, built from env once at startup, fail fast.

No scattered `os.environ` reads elsewhere in `api/` — every other module
takes a `Settings` instance (or reads it off `app.state`).
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from storage.github_sync import GitHubDataSync

DEFAULT_DB_PATH = "data/resourceos.db"
DEFAULT_SEED_PATH = "data/providers_seed.json"


class Settings(BaseModel):
    """Validated application configuration, resolved once at process start."""

    admin_token: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    db_path: str = DEFAULT_DB_PATH
    seed_path: str = DEFAULT_SEED_PATH
    github_repo: str = "sudhir13s/startup-resources-free"
    github_data_token: str | None = None
    data_branch: str = "data"

    def build_sync(self) -> GitHubDataSync | None:
        """Construct the data-branch sync client, or None when no token is set."""
        if not self.github_data_token:
            return None
        return GitHubDataSync(
            repo_slug=self.github_repo,
            token=self.github_data_token,
            branch=self.data_branch,
        )


def _resolve_cors_origins() -> list[str]:
    """Resolve the CORS allow-list from `CORS_ORIGINS` (comma-separated full
    URLs) or `CORS_ORIGIN_HOST` (Render `fromService.host` — a bare
    hostname, scheme added). Falls back to `["*"]` when neither is set
    (local dev only; Render always sets one of the two).

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
    return ["*"]


def load_settings() -> Settings:
    """Build `Settings` from the process environment. Called once at startup."""
    return Settings(
        admin_token=os.environ.get("ADMIN_TOKEN") or None,
        cors_origins=_resolve_cors_origins(),
        db_path=os.environ.get("RESOURCEOS_DB_PATH", DEFAULT_DB_PATH),
        seed_path=os.environ.get("SEED_PATH", DEFAULT_SEED_PATH),
        github_repo=os.environ.get("GITHUB_REPO", "sudhir13s/startup-resources-free"),
        github_data_token=os.environ.get("GITHUB_DATA_TOKEN") or None,
        data_branch=os.environ.get("DATA_BRANCH", "data"),
    )
