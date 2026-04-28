from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

# Make the repo-root `freellm/` package importable when uvicorn runs from
# the `backend/` rootDir on Render. Tests already run with cwd at repo
# root so this is a no-op there.
# Ensure both REPO_ROOT (for `agents`, `schema`, `freellm` packages) AND
# REPO_ROOT/backend (for the bare `import snapshots` / `import db` lines
# below) are on sys.path. Render's blueprint runs uvicorn with
# rootDir=backend, which puts backend/ in sys.path implicitly via cwd —
# but local dev (`uvicorn backend.main:app` from REPO_ROOT) does NOT,
# so we insert it here unconditionally.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for _p in (REPO_ROOT, BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import snapshots as snap_module  # noqa: E402
from freellm import plan as freellm_plan  # noqa: E402
from freellm.providers import PROVIDERS as FREELLM_PROVIDERS  # noqa: E402
from freellm.schemas import ALL_MODALITIES, Modality as FreellmModality  # noqa: E402

SEED_PATH = Path(__file__).parent.parent / "data" / "seed.json"
SERVICE_NAME = "ResourceOS API"
SERVICE_VERSION = "0.1.0"

Tier = Literal[
    "hobby", "personal", "startup-mvp", "pre-seed", "seed", "series-a"
]
GeoPriority = Literal[
    "india-native",
    "accessible-from-india",
    "global-other",
    "us-only",
    "eu-only",
    "other-region",
]
OfferType = Literal[
    "always-free", "free-credits", "free-trial", "free-quota", "grant", "perk", "oss"
]
ParseConfidence = Literal["high", "medium", "low"]


class Provider(BaseModel):
    id: str
    name: str
    category: str
    headline: str
    free_tier_summary: str
    quota_summary: str
    duration_summary: str
    region_summary: str
    offer_type: OfferType
    eligibility_summary: str
    use_case_tiers: list[Tier]
    india_accessible: bool
    geo_priority: GeoPriority
    source_url: str
    parse_confidence: ParseConfidence
    last_verified_at: str
    notes: str | None = None


class TierCount(BaseModel):
    tier: Tier
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class ProvidersResponse(BaseModel):
    total: int
    matched: int
    items: list[Provider]
    tier_counts: list[TierCount]
    category_counts: list[CategoryCount]


def load_seed() -> list[Provider]:
    with SEED_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return [Provider.model_validate(item) for item in raw]


def compute_counts(
    providers: list[Provider],
) -> tuple[list[TierCount], list[CategoryCount]]:
    tier_map: dict[str, int] = {}
    cat_map: dict[str, int] = {}
    for p in providers:
        for t in p.use_case_tiers:
            tier_map[t] = tier_map.get(t, 0) + 1
        cat_map[p.category] = cat_map.get(p.category, 0) + 1
    tier_order: list[Tier] = [
        "hobby", "personal", "startup-mvp", "pre-seed", "seed", "series-a"
    ]
    return (
        [
            TierCount(tier=t, count=tier_map.get(t, 0))
            for t in tier_order
        ],
        sorted(
            [CategoryCount(category=k, count=v) for k, v in cat_map.items()],
            key=lambda c: c.category,
        ),
    )


app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


def _resolve_cors_origins() -> list[str]:
    """Resolve CORS allow-list from CORS_ORIGINS (full URLs, comma-sep) OR
    CORS_ORIGIN_HOST (Render fromService.host — single hostname, scheme added).

    If CORS_ORIGIN_HOST has no dot (e.g. raw service name), auto-append
    `.onrender.com` so a Render service-name entry still produces a valid
    Origin header to match.
    """
    explicit = os.environ.get("CORS_ORIGINS", "").strip()
    if explicit:
        return [o.strip() for o in explicit.split(",") if o.strip()]
    host = os.environ.get("CORS_ORIGIN_HOST", "").strip()
    if host:
        cleaned = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        full = cleaned if "." in cleaned else f"{cleaned}.onrender.com"
        return [f"https://{full}"]
    return ["*"]


allow_origins = _resolve_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """Friendly index — replaces the default 404 at `/` so visitors who
    open the API URL directly see the live service identity + endpoints.
    """
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "ok",
        "endpoints": {
            "health": "/api/health",
            "providers": "/api/providers",
            "openapi": "/openapi.json",
            "docs": "/docs",
        },
        "docs_url": "/docs",
        "github": "https://github.com/sudhir13s/startup-resources-free",
    }


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service_name": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }


@app.get("/api/changes", response_model=snap_module.ChangesResponse)
async def list_changes(
    limit: int = Query(default=200, ge=1, le=1000),
    since: str | None = Query(default=None, description="YYYY-MM-DD lower bound"),
) -> snap_module.ChangesResponse:
    """Reverse-chronological feed of field-level changes between snapshots.

    With <2 snapshots present, returns an empty list (cron writes the
    second snapshot once daily LLM-pipeline keys are configured).
    """
    return snap_module.compute_changes(limit=limit, since=since)


@app.get("/api/snapshots")
async def list_snapshot_dates() -> dict[str, list[str] | str | None]:
    dates = snap_module.list_snapshots()
    return {"dates": dates, "latest": dates[-1] if dates else None}


@app.get("/api/freellm/catalog")
async def freellm_catalog() -> dict:
    """Public-readable view of the freellm catalog.

    Used by the dashboard's Free-LLM-Chain UI to render the chain
    visually. No keys leaked; this is the same data committed to
    `freellm/providers.py`.
    """
    by_modality: dict[str, list[dict]] = {}
    for modality in ALL_MODALITIES:
        rows = []
        for entry in FREELLM_PROVIDERS.get(modality, []):
            rows.append(
                {
                    "provider": entry.provider,
                    "model": entry.model,
                    "env_var": entry.env_var,
                    "speed_tier": entry.speed_tier,
                    "free_tier_kind": entry.free_tier.kind,  # type: ignore[union-attr]
                    "last_verified": entry.last_verified.isoformat(),
                    "docs_url": entry.docs_url,
                    "notes": entry.notes,
                }
            )
        by_modality[modality] = rows
    return {
        "modalities": list(ALL_MODALITIES),
        "total": sum(len(v) for v in by_modality.values()),
        "by_modality": by_modality,
    }


@app.get("/api/freellm/plan")
async def freellm_plan_endpoint(
    modality: FreellmModality = Query(...),
    task_name: str = Query(default="dashboard-preview"),
) -> dict:
    """Dry-run routing plan for the given modality.

    Returns the chain that WOULD be tried, in order, given the env vars
    actually present on this server. Safe to call cheaply — no LiteLLM
    invocation, no network. The dashboard's "Test the chain" button
    calls this and renders `chosen` + `options`.
    """
    plan = freellm_plan(modality=modality, task_name=task_name)
    return plan.model_dump()


@app.get("/api/providers", response_model=ProvidersResponse)
async def list_providers(
    tier: Tier | None = Query(default=None),
    india: bool | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    offer_type: list[OfferType] | None = Query(default=None),
    min_confidence: ParseConfidence | None = Query(default=None),
) -> ProvidersResponse:
    providers = load_seed()
    matched = providers

    if tier is not None:
        matched = [p for p in matched if tier in p.use_case_tiers]
    if india is True:
        matched = [p for p in matched if p.india_accessible]
    if category:
        cats = set(category)
        matched = [p for p in matched if p.category in cats]
    if offer_type:
        offers = set(offer_type)
        matched = [p for p in matched if p.offer_type in offers]
    if min_confidence is not None:
        rank = {"high": 3, "medium": 2, "low": 1}
        threshold = rank[min_confidence]
        matched = [p for p in matched if rank[p.parse_confidence] >= threshold]

    tier_counts, category_counts = compute_counts(providers)
    return ProvidersResponse(
        total=len(providers),
        matched=len(matched),
        items=matched,
        tier_counts=tier_counts,
        category_counts=category_counts,
    )


# =====================================================================
# Verify queue API (B9)
# =====================================================================
#
# The pipeline orchestrator (B3) drops low-confidence ProviderRecord rows
# into the `verify_queue` SQLite table. These endpoints expose that queue
# to the dashboard's Verify tab + drive the Confirm/Reject keyboard
# shortcuts wired in the UI.
#
# When the DB file does not exist (Render Web Service today, before the
# cron writes it for the first time), the endpoints return empty lists /
# 404s rather than 500s.

from fastapi import HTTPException  # noqa: E402

# `db` lives at backend/db.py. Imported lazily so a missing sqlite3 (won't
# happen on Python 3.11+) doesn't break the FastAPI module load.


class VerifyQueueItem(BaseModel):
    record_id: str
    provider_id: str
    provider_name: str
    source_url: str
    parse_confidence: ParseConfidence
    reason: str
    queued_at: str


class VerifyQueueResponse(BaseModel):
    total: int
    items: list[VerifyQueueItem]


class VerifyResolveResponse(BaseModel):
    record_id: str
    status: Literal["confirmed", "rejected"]
    resolved_by: str | None = None


def _db_available() -> bool:
    import db as db_module  # type: ignore[import-untyped]

    return db_module.db_path().exists()


@app.get("/api/verify-queue", response_model=VerifyQueueResponse)
async def list_verify_queue() -> VerifyQueueResponse:
    """Return all `pending` rows from the verify queue, oldest first."""
    if not _db_available():
        return VerifyQueueResponse(total=0, items=[])

    import db as db_module  # type: ignore[import-untyped]

    with db_module.db_session() as conn:
        rows = db_module.pending_verify(conn)
    items = [VerifyQueueItem(**r) for r in rows]
    return VerifyQueueResponse(total=len(items), items=items)


@app.post(
    "/api/verify-queue/{record_id}/confirm",
    response_model=VerifyResolveResponse,
)
async def confirm_verify(
    record_id: str,
    resolved_by: str | None = Query(default=None, max_length=80),
) -> VerifyResolveResponse:
    return _resolve(record_id, status="confirmed", resolved_by=resolved_by)


@app.post(
    "/api/verify-queue/{record_id}/reject",
    response_model=VerifyResolveResponse,
)
async def reject_verify(
    record_id: str,
    resolved_by: str | None = Query(default=None, max_length=80),
) -> VerifyResolveResponse:
    return _resolve(record_id, status="rejected", resolved_by=resolved_by)


def _resolve(
    record_id: str,
    *,
    status: Literal["confirmed", "rejected"],
    resolved_by: str | None,
) -> VerifyResolveResponse:
    if not _db_available():
        raise HTTPException(
            status_code=404,
            detail="verify queue database not initialized yet",
        )

    import db as db_module  # type: ignore[import-untyped]

    with db_module.db_session() as conn:
        ok = db_module.resolve_verify(
            conn, record_id, status=status, resolved_by=resolved_by
        )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"no pending verify item for record_id={record_id!r}",
        )
    return VerifyResolveResponse(
        record_id=record_id,
        status=status,
        resolved_by=resolved_by,
    )
