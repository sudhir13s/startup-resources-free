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

Tier = Literal["hobby", "personal", "startup-mvp", "startup"]
GeoPriority = Literal[
    "india-native",
    "accessible-from-india",
    "global-other",
    "us-only",
    "eu-only",
    "other-region",
]


class Provider(BaseModel):
    id: str
    name: str
    category: str
    headline: str
    free_tier_summary: str
    use_case_tiers: list[Tier]
    india_accessible: bool
    geo_priority: GeoPriority
    source_url: str
    parse_confidence: Literal["high", "medium", "low"]
    last_verified_at: str
    notes: str | None = None


class ProvidersResponse(BaseModel):
    total: int
    matched: int
    items: list[Provider]


def load_seed() -> list[Provider]:
    with SEED_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return [Provider.model_validate(item) for item in raw]


app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
    category: str | None = Query(default=None),
) -> ProvidersResponse:
    providers = load_seed()
    matched = providers

    if tier is not None:
        matched = [p for p in matched if tier in p.use_case_tiers]
    if india is True:
        matched = [p for p in matched if p.india_accessible]
    if category is not None:
        matched = [p for p in matched if p.category == category]

    return ProvidersResponse(total=len(providers), matched=len(matched), items=matched)
