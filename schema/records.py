"""Canonical ProviderRecord Pydantic model.

Maps 1:1 to the spec in `.claude/rules/project/provider-schema.md`.

Backward-compat: every field added beyond what `data/seed.json` already
carries is OPTIONAL with a default, so the existing 40-record seed loads
through `record_from_seed()` without rewrites.

Forward-compat: adding an optional field bumps `schema/VERSION` only.
Adding required, renaming, or changing enum membership requires a
migration script under `schema/migrations/<NNN>-<slug>.{sql,py}`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# === Locked enums ===
# Keep in sync with provider-schema.md. Tests assert the membership lists
# below match the spec rule.

Category = Literal[
    "cloud",
    "hosting",  # legacy synonym for cloud — present in seed.json; map at ingest
    "gpu",
    "ai-api",
    "database",
    "storage",
    "auth",
    "observability",
    "domain",
    "startup-credit",
    "grant",
    "accelerator",
    "perk",
    "oss",
    "learning",
]

OfferType = Literal[
    "always-free",  # legacy synonym for free-tier — kept for seed compat
    "free-tier",
    "free-credits",
    "free-trial",
    "free-quota",
    "grant",
    "perk",
    "oss",
]

AccessMethod = Literal[
    "api-key",
    "oauth",
    "signup",
    "email-verify",
    "github-auth",
    "manual-apply",
    "invite-only",
    "unknown",
]

GeoPriority = Literal[
    "india-native",
    "accessible-from-india",
    "global-other",
    "us-only",
    "eu-only",
    "other-region",
]

UseCaseTier = Literal[
    "hobby",
    "personal",
    "startup-mvp",
    "pre-seed",
    "seed",
    "series-a",
]

ParseConfidence = Literal["high", "medium", "low"]

SourceMethod = Literal["api", "rss", "structured-html", "regex-html", "manual", "llm"]

Status = Literal["active", "reduced", "ended", "unknown"]

CardVariant = Literal["resource", "funds"]

# Categories that route to the /funds view (programs that GIVE you money:
# grants, startup credits, accelerators, partner perks). Everything else
# routes to /resources (things you USE: cloud / GPU / DB / LLM-API / …).
# Both canonical singular slugs AND legacy plural seed slugs are listed
# so the discriminator works regardless of ingest path.
_FUND_CATEGORIES: frozenset[str] = frozenset(
    {
        "grant",
        "grants",
        "startup-credit",
        "startup-credits",
        "accelerator",
        "accelerators",
        "perk",
        "perks",
    }
)


def category_card_variant(category: str) -> CardVariant:
    """Map a category slug → card_variant ('resource' | 'funds').

    Pure function — single source of truth shared by ProviderRecord,
    backend/main.py's Provider model, and any future frontend codepath
    that needs to discriminate at ingest time.
    """
    return "funds" if category in _FUND_CATEGORIES else "resource"


# === Eligibility sub-shape ===


class Eligibility(BaseModel):
    """Eligibility rules — drives filter logic + UI badges."""

    model_config = ConfigDict(extra="forbid")

    regions: list[str] = Field(default_factory=lambda: ["global"])
    user_types: list[str] = Field(default_factory=lambda: ["any"])
    company_age_max_years: int | None = None
    funding_max_usd: float | None = None


# === Canonical record ===


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ProviderRecord(BaseModel):
    """Canonical provider offering.

    Every collector emits this. Every UI / API consumes this.
    History is append-only — re-scrape produces a NEW record (new `id`)
    pointing at the previous via `supersedes_id`.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Identity ---
    id: str  # uuid; stable across re-scrapes via deterministic hashing
    provider_id: str  # slug, stable, unique within a category
    provider_name: str  # display name

    category: Category
    subcategory: str | None = None
    source_url: str

    # --- The offering ---
    offer_type: OfferType
    offer_summary: str  # one-liner; "free_tier_summary" in seed.json
    headline: str | None = None  # punchier marketing line shown above offer_summary
    currency: str | None = None  # ISO 4217
    credit_amount: float | None = None
    credit_duration_days: int | None = None

    limits: dict[str, Any] = Field(default_factory=dict)

    # --- UI stat tiles (≤ 30 chars each per spec) ---
    quota_summary: str = "—"
    duration_summary: str = "—"
    region_summary: str = "—"
    eligibility_summary: str = "—"

    # --- Eligibility + access ---
    access_method: AccessMethod = "unknown"
    eligibility: Eligibility = Field(default_factory=Eligibility)
    restrictions: str | None = None

    # --- Geographic + tier fit ---
    geo_priority: GeoPriority = "global-other"
    india_accessible: bool = True  # seed.json carries this; convenience for UI
    use_case_tiers: list[UseCaseTier] = Field(default_factory=list)
    tier_fit_rationale: str | None = None

    # --- Quality / freshness ---
    scraped_at: datetime = Field(default_factory=_utcnow)
    parse_confidence: ParseConfidence = "low"
    source_method: SourceMethod = "manual"
    last_verified_at: date | None = None
    expiry_date: date | None = None

    # --- Status + history pointers ---
    status: Status = "active"
    supersedes_id: str | None = None
    notes: str | None = None

    # --- Computed discriminator ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def card_variant(self) -> CardVariant:
        """Routes the record to the right UI view + card schema.

        `funds` → things that GIVE you money (grants, credits,
        accelerators, perks) → /funds page, FundCard layout.
        `resource` → things you USE (cloud, GPU, DB, AI APIs, …) →
        /resources page, ResourceCard layout.

        Derived (not stored) — frontend reads `record.card_variant`.
        """
        return category_card_variant(self.category)

    # --- Validators ---

    @field_validator("currency")
    @classmethod
    def _currency_iso(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError(f"currency must be ISO 4217 (3 letters), got {v!r}")
        return v

    @field_validator("source_url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"source_url must be http(s) URL, got {v!r}")
        return v

    @field_validator(
        "quota_summary", "duration_summary", "region_summary", "eligibility_summary"
    )
    @classmethod
    def _short_tiles(cls, v: str) -> str:
        # Spec guidance: ≤ 30 chars for the card stat tiles. We allow up to
        # 40 so the existing seed (which has a 32-char eligibility line)
        # loads, while still forcing extractor-emitted records to stay
        # punchy. Anything longer is almost certainly model verbosity.
        if len(v) > 40:
            raise ValueError(
                f"stat-tile field exceeds 40 chars ({len(v)}): {v!r}. "
                "Tile layout truncates; aim for ≤ 30."
            )
        return v

    @field_validator("limits", mode="before")
    @classmethod
    def _coerce_limits(cls, v: Any, info) -> dict[str, Any]:
        """Run raw `limits` through the per-category typed model.

        Resolves Architect B1 (9/10) + B2 (8/10) from the 2026-04-28
        schema-flexibility roundtable: the canonical-key registry
        (`schema.limits.LIMITS_MODELS`) coerces declared keys to their
        typed shapes and lets non-canonical keys pass through unchanged.

        Numeric strings are coerced to numbers; booleans coerced from
        truthy strings; arrays preserved. This catches extractor
        artifacts at write time rather than at sort/filter query time.

        `mode='before'` runs against the raw input dict. `category` is
        read from `info.data` — only valid because `category` is declared
        before `limits` in the model.
        """
        from schema.limits import validate_limits

        if v is None:
            return {}
        if not isinstance(v, dict):
            return v
        category = info.data.get("category", "")
        return validate_limits(category, v)

    # --- Adapters ---

    def to_seed_shape(self) -> dict[str, Any]:
        """Project back into the legacy seed.json shape so the existing
        FastAPI route + Next.js card UI continue to work unchanged.
        """
        return {
            "id": self.provider_id,
            "name": self.provider_name,
            "category": self.category,
            "card_variant": self.card_variant,
            "headline": self.headline or self.offer_summary,
            "free_tier_summary": self.offer_summary,
            "quota_summary": self.quota_summary,
            "duration_summary": self.duration_summary,
            "region_summary": self.region_summary,
            "offer_type": self.offer_type,
            "eligibility_summary": self.eligibility_summary,
            "use_case_tiers": list(self.use_case_tiers),
            "india_accessible": self.india_accessible,
            "geo_priority": self.geo_priority,
            "source_url": self.source_url,
            "parse_confidence": self.parse_confidence,
            "last_verified_at": (
                self.last_verified_at.isoformat() if self.last_verified_at else None
            ),
            "notes": self.notes,
        }


# === Adapter for existing seed.json ===


# Legacy seed.json uses pluralized + alternate slugs. Normalize at ingest
# so the canonical schema remains the spec-aligned form.
_SEED_CATEGORY_ALIASES: dict[str, Category] = {
    "databases": "database",
    "grants": "grant",
    "accelerators": "accelerator",
    "startup-credits": "startup-credit",
    "perks": "perk",
}


def record_from_seed(row: dict[str, Any]) -> ProviderRecord:
    """Inflate a seed.json row into a full ProviderRecord.

    The seed shape is a strict subset of ProviderRecord; missing fields
    take model defaults. `id` and `provider_id` both derive from the
    seed `id` slug since seed rows are hand-curated (one snapshot only).
    """
    slug = row["id"]
    last_verified = row.get("last_verified_at")
    raw_category = row["category"]
    category = _SEED_CATEGORY_ALIASES.get(raw_category, raw_category)
    return ProviderRecord(
        id=f"seed:{slug}",
        provider_id=slug,
        provider_name=row["name"],
        category=category,
        source_url=row["source_url"],
        offer_type=row["offer_type"],
        offer_summary=row.get("free_tier_summary") or row.get("headline", ""),
        headline=row.get("headline"),
        quota_summary=row.get("quota_summary", "—"),
        duration_summary=row.get("duration_summary", "—"),
        region_summary=row.get("region_summary", "—"),
        eligibility_summary=row.get("eligibility_summary", "—"),
        india_accessible=bool(row.get("india_accessible", True)),
        geo_priority=row.get("geo_priority", "global-other"),
        use_case_tiers=list(row.get("use_case_tiers", [])),
        parse_confidence=row.get("parse_confidence", "high"),
        source_method="manual",
        last_verified_at=date.fromisoformat(last_verified) if last_verified else None,
        notes=row.get("notes"),
    )
