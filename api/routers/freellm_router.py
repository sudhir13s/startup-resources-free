"""`GET /api/freellm/catalog` and `GET /api/freellm/plan` — ported unchanged from `backend/main.py`."""

from __future__ import annotations

from fastapi import APIRouter, Query

from freellm import plan as freellm_plan
from freellm.providers import PROVIDERS as FREELLM_PROVIDERS
from freellm.schemas import ALL_MODALITIES
from freellm.schemas import Modality as FreellmModality

router = APIRouter(prefix="/api/freellm", tags=["freellm"])


@router.get("/catalog")
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


@router.get("/plan")
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
    result = freellm_plan(modality=modality, task_name=task_name)
    return result.model_dump()
