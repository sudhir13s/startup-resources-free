"""ProviderRecord v2 — one vendor offer, broken down per service.

A record is an *offer* (AWS Free Tier, AWS Activate, Groq free quota).
Multi-service offers list each service in `services[]` with its own
category, so AWS Free Tier also matches the Database / Storage / AI filters
through the computed `categories` field.

Version history (append-only) is a storage concern: this model carries no
row id. `storage/` stores each accepted change as a new version.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from domain.taxonomy import (
    INDIA_USABLE_GEO,
    AccessMethod,
    CardVariant,
    Category,
    GeoPriority,
    LimitPeriod,
    OfferType,
    ParseConfidence,
    PricingLayer,
    ResourceCategory,
    SourceMethod,
    Status,
    UseCaseTier,
    card_variant,
    normalize_category,
    normalize_offer_type,
)

TILE_MAX_CHARS = 40  # UI stat tiles; aim for <= 30
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Limit(BaseModel):
    """One display-ready quota line, e.g. 750 hours / month."""

    model_config = ConfigDict(extra="forbid")

    label: str                          # human label: "t3.micro instance hours"
    value: float | int | str | bool     # 750 · "MySQL, PostgreSQL" · True
    unit: str | None = None             # "hours", "GB", "requests", "MAU", "USD"
    period: LimitPeriod | None = None   # per month / day / once …
    note: str | None = None


class Service(BaseModel):
    """One service inside an offer (EC2, RDS, S3, Workers, Llama 3.3 70B …)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: ResourceCategory
    service_type: str | None = None     # vm · serverless · sql · nosql · object-storage · llm …
    pricing_layer: PricingLayer = "always-free"
    summary: str
    limits: list[Limit] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _canonical_category(cls, v: Any) -> Any:
        return normalize_category(v) if isinstance(v, str) else v


class Credit(BaseModel):
    """A money or credit grant, e.g. $1,000 AWS Activate Founders."""

    model_config = ConfigDict(extra="forbid")

    label: str
    amount: float | None = None
    currency: str | None = None         # ISO 4217
    duration_days: int | None = None
    conditions: str | None = None

    @field_validator("currency")
    @classmethod
    def _iso_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError(f"currency must be ISO 4217, got {v!r}")
        return v


class Link(BaseModel):
    """A verified link shown in the detail view (never a guessed URL)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    url: str

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"url must be http(s), got {v!r}")
        return v


class Eligibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regions: list[str] = Field(default_factory=lambda: ["global"])
    user_types: list[str] = Field(default_factory=lambda: ["any"])
    company_age_max_years: int | None = None
    funding_max_usd: float | None = None


class ProviderRecord(BaseModel):
    """Canonical offer record. Every collector emits it; every view reads it."""

    model_config = ConfigDict(extra="forbid")

    # --- Identity ---
    provider_id: str = Field(pattern=SLUG_PATTERN)
    name: str
    vendor: str                                   # groups offers: "AWS", "Supabase"
    category: Category                            # primary category
    source_urls: list[str] = Field(min_length=1)  # pages the refresh reads

    # --- The offer ---
    offer_type: OfferType
    headline: str                                 # one line under the name
    highlights: list[str] = Field(default_factory=list)  # TL;DR bullets, <= 6
    services: list[Service] = Field(default_factory=list)
    credits: list[Credit] = Field(default_factory=list)

    # --- Card stat tiles ---
    quota_summary: str = "—"
    duration_summary: str = "—"
    region_summary: str = "—"
    eligibility_summary: str = "—"

    # --- Eligibility, access, caveats ---
    eligibility: Eligibility = Field(default_factory=Eligibility)
    access_method: AccessMethod = "unknown"
    claim_steps: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    gotchas: list[str] = Field(default_factory=list)
    after_free_period: str | None = None
    links: list[Link] = Field(default_factory=list)

    # --- Fit ---
    geo_priority: GeoPriority = "global-other"
    always_on: bool | None = None
    use_case_tiers: list[UseCaseTier] = Field(min_length=1)
    tier_fit_rationale: str | None = None

    # --- Quality / freshness ---
    parse_confidence: ParseConfidence = "medium"
    source_method: SourceMethod = "manual"
    last_verified_at: date | None = None
    scraped_at: datetime = Field(default_factory=_utcnow)
    expiry_date: date | None = None
    status: Status = "active"
    notes: str | None = None

    # --- Derived (serialized for the API; never stored as input) ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def categories(self) -> list[str]:
        """Primary category plus every service category — what filters match on."""
        found = {self.category, *(s.category for s in self.services)}
        return sorted(found)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def card_variant(self) -> CardVariant:
        return card_variant(self.category)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def india_accessible(self) -> bool:
        return self.geo_priority in INDIA_USABLE_GEO

    # --- Validators ---

    @field_validator("category", mode="before")
    @classmethod
    def _canonical_category(cls, v: Any) -> Any:
        return normalize_category(v) if isinstance(v, str) else v

    @field_validator("offer_type", mode="before")
    @classmethod
    def _canonical_offer_type(cls, v: Any) -> Any:
        return normalize_offer_type(v) if isinstance(v, str) else v

    @field_validator("access_method", mode="before")
    @classmethod
    def _unknown_access_method(cls, v: Any) -> Any:
        # LLMs invent values; coerce instead of failing the whole record.
        allowed = AccessMethod.__args__  # type: ignore[attr-defined]
        return v if v in allowed else "unknown"

    @field_validator("source_urls")
    @classmethod
    def _http_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"source_urls must be http(s), got {url!r}")
        return v

    @field_validator(
        "quota_summary", "duration_summary", "region_summary", "eligibility_summary"
    )
    @classmethod
    def _short_tile(cls, v: str) -> str:
        if len(v) > TILE_MAX_CHARS:
            raise ValueError(f"stat tile over {TILE_MAX_CHARS} chars: {v!r}")
        return v

    @field_validator("highlights")
    @classmethod
    def _few_highlights(cls, v: list[str]) -> list[str]:
        if len(v) > 6:
            raise ValueError("highlights holds at most 6 bullets")
        return v

    # --- Serialization helpers ---

    def to_storage(self) -> dict[str, Any]:
        """JSON-safe dict without derived fields — what storage persists."""
        return self.model_dump(
            mode="json", exclude={"categories", "card_variant", "india_accessible"}
        )

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> ProviderRecord:
        clean = {
            k: v for k, v in data.items()
            if k not in {"categories", "card_variant", "india_accessible"}
        }
        return cls.model_validate(clean)

    def content_fingerprint(self) -> dict[str, Any]:
        """Fields that define the offer — used to decide if a new version is needed.

        Excludes freshness metadata so a re-verify without changes stores nothing.
        """
        return self.model_dump(
            mode="json",
            exclude={
                "categories", "card_variant", "india_accessible",
                "scraped_at", "last_verified_at", "parse_confidence", "source_method",
            },
        )
