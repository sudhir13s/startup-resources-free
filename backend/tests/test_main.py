from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the backend package importable when pytest is invoked from repo root.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app, load_seed  # noqa: E402

client = TestClient(app)

ALL_TIERS = ["hobby", "personal", "startup-mvp", "pre-seed", "seed", "series-a"]
ALL_OFFER_TYPES = [
    "always-free",
    "free-credits",
    "free-trial",
    "free-quota",
    "grant",
    "perk",
    "oss",
]


# ---------- / (friendly index) ----------


def test_root_returns_service_index():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "ResourceOS API"
    assert body["status"] == "ok"
    assert "/api/health" in body["endpoints"]["health"]
    assert "/api/providers" in body["endpoints"]["providers"]


# ---------- /api/health ----------


def test_health_returns_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service_name"] == "ResourceOS API"


# ---------- /api/providers basic ----------


def test_providers_returns_seed():
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 20
    assert body["matched"] == body["total"]
    assert isinstance(body["items"], list)
    assert len(body["items"]) == body["matched"]


def test_providers_response_includes_tier_counts():
    body = client.get("/api/providers").json()
    counts = {tc["tier"]: tc["count"] for tc in body["tier_counts"]}
    for t in ALL_TIERS:
        assert t in counts
    # Total appearances may exceed total providers because tiers are multi-valued.
    assert sum(counts.values()) >= body["total"]


def test_providers_response_includes_category_counts():
    body = client.get("/api/providers").json()
    cats = {cc["category"]: cc["count"] for cc in body["category_counts"]}
    assert "ai-api" in cats
    assert sum(cats.values()) == body["total"]


# ---------- filters ----------


@pytest.mark.parametrize("tier", ALL_TIERS)
def test_filter_by_tier_only_returns_matching_records(tier: str):
    body = client.get(f"/api/providers?tier={tier}").json()
    for p in body["items"]:
        assert tier in p["use_case_tiers"]


def test_filter_by_invalid_tier_returns_422():
    r = client.get("/api/providers?tier=enterprise")
    assert r.status_code == 422


def test_filter_india_true_returns_only_india_accessible():
    body = client.get("/api/providers?india=true").json()
    assert body["matched"] >= 1
    for p in body["items"]:
        assert p["india_accessible"] is True


def test_filter_category_multi_value_or():
    body = client.get(
        "/api/providers?category=ai-api&category=databases"
    ).json()
    for p in body["items"]:
        assert p["category"] in {"ai-api", "databases"}


def test_filter_offer_type_grant_returns_only_grants():
    body = client.get("/api/providers?offer_type=grant").json()
    for p in body["items"]:
        assert p["offer_type"] == "grant"


def test_filter_offer_type_invalid_returns_422():
    r = client.get("/api/providers?offer_type=enterprise")
    assert r.status_code == 422


def test_min_confidence_high_excludes_lower():
    body = client.get("/api/providers?min_confidence=high").json()
    for p in body["items"]:
        assert p["parse_confidence"] == "high"


def test_min_confidence_medium_excludes_low_only():
    body = client.get("/api/providers?min_confidence=medium").json()
    for p in body["items"]:
        assert p["parse_confidence"] in {"high", "medium"}


def test_combined_filter_tier_plus_india_plus_category():
    body = client.get(
        "/api/providers?tier=startup-mvp&india=true&category=ai-api"
    ).json()
    for p in body["items"]:
        assert "startup-mvp" in p["use_case_tiers"]
        assert p["india_accessible"] is True
        assert p["category"] == "ai-api"


# ---------- seed integrity ----------


def test_seed_loads_without_error():
    seed = load_seed()
    assert len(seed) >= 20


def test_every_seed_record_has_required_fields():
    seed = load_seed()
    for p in seed:
        assert p.id
        assert p.name
        assert p.category
        assert p.headline
        assert p.quota_summary
        assert p.duration_summary
        assert p.region_summary
        assert p.eligibility_summary
        assert p.offer_type in ALL_OFFER_TYPES
        assert p.parse_confidence in {"high", "medium", "low"}
        assert len(p.use_case_tiers) >= 1
        assert all(t in ALL_TIERS for t in p.use_case_tiers)


def test_every_seed_id_is_unique():
    seed = load_seed()
    ids = [p.id for p in seed]
    assert len(ids) == len(set(ids))


def test_india_native_records_are_india_accessible():
    seed = load_seed()
    for p in seed:
        if p.geo_priority == "india-native":
            assert p.india_accessible is True


def test_at_least_one_record_per_offer_type_we_use():
    seed = load_seed()
    used = {p.offer_type for p in seed}
    # Seed currently exercises these five (perk + oss are valid enum members
    # but optional in v0.1).
    assert {"always-free", "free-quota", "free-credits", "free-trial", "grant"}.issubset(used)


# ---------- CORS env resolution ----------


def test_cors_resolves_explicit_origins(monkeypatch: pytest.MonkeyPatch):
    """CORS_ORIGINS (full URLs, comma-sep) wins over CORS_ORIGIN_HOST."""
    import importlib

    monkeypatch.setenv("CORS_ORIGINS", "https://a.example,https://b.example")
    monkeypatch.setenv("CORS_ORIGIN_HOST", "ignored.example")
    import main as fresh

    importlib.reload(fresh)
    assert fresh.allow_origins == ["https://a.example", "https://b.example"]


def test_cors_resolves_host_with_https_prefix(monkeypatch: pytest.MonkeyPatch):
    """CORS_ORIGIN_HOST is host-only — module prepends https://."""
    import importlib

    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("CORS_ORIGIN_HOST", "startup-resources.onrender.com")
    import main as fresh

    importlib.reload(fresh)
    assert fresh.allow_origins == ["https://startup-resources.onrender.com"]


def test_cors_falls_back_to_wildcard(monkeypatch: pytest.MonkeyPatch):
    import importlib

    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ORIGIN_HOST", raising=False)
    import main as fresh

    importlib.reload(fresh)
    assert fresh.allow_origins == ["*"]
