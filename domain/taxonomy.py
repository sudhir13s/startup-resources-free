"""Enums, display labels, and legacy-slug normalisation.

Single source of truth for every slug the API accepts and the UI renders.
The frontend mirrors these in `frontend/lib/types.ts`; a test keeps them equal.
"""

from __future__ import annotations

from typing import Literal, get_args

# Things you USE (rendered on /resources). Also valid as a service category.
ResourceCategory = Literal[
    "cloud",          # compute, hosting, PaaS, serverless, networking
    "gpu",
    "ai-api",
    "database",
    "storage",
    "auth",
    "observability",
    "domain",         # domains, DNS, email
    "dev-tools",      # CI/CD, repos, codespaces
    "oss",
    "learning",
]

# Programs that GIVE you money or discounts (rendered on /funds).
FundCategory = Literal["startup-credit", "grant", "accelerator", "perk"]

Category = Literal[
    "cloud", "gpu", "ai-api", "database", "storage", "auth", "observability",
    "domain", "dev-tools", "oss", "learning",
    "startup-credit", "grant", "accelerator", "perk",
]

OfferType = Literal[
    "free-tier",     # always-free or free plan with no expiry
    "free-credits",  # currency credits that expire
    "free-trial",    # full access, time-limited
    "free-quota",    # API request/token quota that refills
    "grant",
    "perk",
    "oss",
]

# How a single service inside an offer is free.
PricingLayer = Literal["always-free", "12-month", "trial", "credit", "quota"]

LimitPeriod = Literal["minute", "hour", "day", "month", "year", "once", "total"]

AccessMethod = Literal[
    "api-key", "oauth", "signup", "email-verify", "github-auth",
    "manual-apply", "invite-only", "contact-sales", "unknown",
]

GeoPriority = Literal[
    "india-native", "accessible-from-india", "global-other",
    "us-only", "eu-only", "other-region",
]

UseCaseTier = Literal["hobby", "personal", "startup-mvp", "pre-seed", "seed", "series-a"]

ParseConfidence = Literal["high", "medium", "low"]

SourceMethod = Literal["manual", "llm", "api"]

Status = Literal["active", "reduced", "ended", "unknown"]

CardVariant = Literal["resource", "funds"]

RESOURCE_CATEGORIES: tuple[str, ...] = get_args(ResourceCategory)
FUND_CATEGORIES: tuple[str, ...] = get_args(FundCategory)
CATEGORIES: tuple[str, ...] = get_args(Category)
OFFER_TYPES: tuple[str, ...] = get_args(OfferType)
USE_CASE_TIERS: tuple[str, ...] = get_args(UseCaseTier)
GEO_PRIORITIES: tuple[str, ...] = get_args(GeoPriority)

CONFIDENCE_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}

# Geo values a person in India can use. Drives the derived `india_accessible`.
INDIA_USABLE_GEO: frozenset[str] = frozenset(
    {"india-native", "accessible-from-india", "global-other"}
)

CATEGORY_LABELS: dict[str, str] = {
    "cloud": "Cloud & Hosting",
    "gpu": "GPU & Notebooks",
    "ai-api": "AI APIs",
    "database": "Databases",
    "storage": "Storage",
    "auth": "Auth",
    "observability": "Observability",
    "domain": "Domains & Email",
    "dev-tools": "Dev Tools",
    "oss": "Open Source",
    "learning": "Learning",
    "startup-credit": "Startup Credits",
    "grant": "Grants",
    "accelerator": "Accelerators",
    "perk": "Perks",
}

# Legacy slugs found in seed.json / old snapshots / LLM output → canonical.
_CATEGORY_ALIASES: dict[str, str] = {
    "hosting": "cloud",
    "databases": "database",
    "grants": "grant",
    "accelerators": "accelerator",
    "startup-credits": "startup-credit",
    "perks": "perk",
    "domains": "domain",
}
_OFFER_TYPE_ALIASES: dict[str, str] = {"always-free": "free-tier"}


def normalize_category(value: str) -> str:
    """Map a legacy or plural category slug to its canonical form."""
    return _CATEGORY_ALIASES.get(value, value)


def normalize_offer_type(value: str) -> str:
    """Map a legacy offer-type slug to its canonical form."""
    return _OFFER_TYPE_ALIASES.get(value, value)


def card_variant(category: str) -> CardVariant:
    """Which view a record belongs to: /funds for money programs, else /resources."""
    return "funds" if category in FUND_CATEGORIES else "resource"
