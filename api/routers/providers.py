"""`GET /api/providers` and `GET /api/providers/{provider_id}`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_repository
from api.services.catalog_service import (
    UnknownCategoryError,
    get_provider_detail,
    list_providers,
    normalize_categories,
)
from domain.filters import Facets, ProviderFilter
from domain.records import ProviderRecord
from domain.taxonomy import CardVariant, GeoPriority, OfferType, ParseConfidence, UseCaseTier
from storage.repository import Repository

router = APIRouter(prefix="/api", tags=["providers"])


class VersionSummaryOut(BaseModel):
    version: int
    source: str
    run_id: str | None
    created_at: str


class RelatedProvider(BaseModel):
    provider_id: str
    name: str
    category: str
    offer_type: str


class ProviderDetailResponse(BaseModel):
    record: ProviderRecord
    history: list[VersionSummaryOut]
    related: list[RelatedProvider]


class ProvidersResponse(BaseModel):
    total: int
    matched: int
    items: list[ProviderRecord]
    facets: Facets


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers(
    repository: Repository = Depends(get_repository),
    variant: CardVariant | None = Query(default=None),
    tier: list[UseCaseTier] = Query(default_factory=list),
    category: list[str] = Query(default_factory=list),
    offer_type: list[OfferType] = Query(default_factory=list),
    geo: list[GeoPriority] = Query(default_factory=list),
    min_confidence: ParseConfidence | None = Query(default=None),
    q: str | None = Query(default=None),
) -> ProvidersResponse:
    """Filtered + faceted catalog listing. Invalid enum values are rejected by
    FastAPI's own query validation (422) before this function runs; only
    category slugs need explicit normalization since they accept aliases.
    """
    try:
        categories = normalize_categories(category)
    except UnknownCategoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    flt = ProviderFilter(
        variant=variant,
        tiers=tier,
        categories=categories,
        offer_types=offer_type,
        geo=geo,
        min_confidence=min_confidence,
        query=q,
    )
    total, items, facets = list_providers(repository, flt)
    return ProvidersResponse(total=total, matched=len(items), items=items, facets=facets)


@router.get("/providers/{provider_id}", response_model=ProviderDetailResponse)
async def get_provider(
    provider_id: str, repository: Repository = Depends(get_repository)
) -> ProviderDetailResponse:
    result = get_provider_detail(repository, provider_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown provider_id: {provider_id!r}")
    record, history, related = result
    return ProviderDetailResponse(
        record=record,
        history=[
            VersionSummaryOut(
                version=v.version,
                source=v.source,
                run_id=v.run_id,
                created_at=v.created_at.isoformat(),
            )
            for v in history
        ],
        related=[
            RelatedProvider(
                provider_id=r.provider_id,
                name=r.name,
                category=r.category,
                offer_type=r.offer_type,
            )
            for r in related
        ],
    )
