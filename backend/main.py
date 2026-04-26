from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
