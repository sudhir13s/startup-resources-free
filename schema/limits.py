"""Per-category typed limits models.

Resolves the CRITICAL findings from the 2026-04-28 schema-flexibility
roundtable:

- **Architect B1 (9/10):** the canonical-keys "registry" must be machine-
  readable Pydantic `BaseModel` subclasses, not a `dict[str, type]` runtime
  comment. The agentic extractor (`agents/extractor.py`, future v0.2)
  passes `LIMITS_MODELS[record.category]` as `response_model` to LiteLLM.
  Without typed models the extractor falls back to untyped dict and we
  lose coercion + the `parse_confidence: low` escalation.

- **Architect B2 (8/10):** limit values must be typed numerics (`int | None`,
  `float | None`), not `Any`. Otherwise extractor-emitted strings like
  `"14,400/day"` slip through and silently kill dashboard sort/filter
  queries — invisible bug until users see filters return zero records.

Design (per roundtable consolidation, `docs/discussions/2026-04-28T13-55-roundtable-schema-flexibility/README.md`):

- 15 typed `BaseModel` subclasses, one per category in `schema.records.Category`.
- All fields `Optional` with `None` defaults — partial extractions are
  valid and expected (a provider that only publishes 3 of 7 canonical
  fields is still a useful record).
- `model_config = ConfigDict(extra="allow")` — non-canonical keys pass
  through unchanged. Type protection applies to canonical keys; extras
  are best-effort. This is the "convention not validation" promise.
- `LIMITS_MODELS: dict[str, type[BaseModel]]` registry keyed by category
  slug, including legacy plural slugs (`grants` → GrantLimits) so the
  extractor and ingest path don't have to normalize first.
- `validate_limits(category, raw)` utility: round-trips raw dict through
  the typed model, returns `.model_dump(exclude_none=True)`. This is what
  `ProviderRecord` uses as a `@field_validator('limits', mode='before')`.
- `ProviderRecord.limits` stays typed `dict[str, Any]` for storage
  (jsonb-friendly, frontend-flexible). The typed model is the
  ingest/extractor contract, not the DB column type.

Adding a new canonical key for a category: append the field to the
relevant `*Limits` class. No migration. No seed changes. No frontend
changes (the `LimitsView` renders any shape).

Adding a new category: add a new `*Limits` class + register it in
`LIMITS_MODELS` keyed by every slug variant. Update `Category` Literal
in `schema/records.py`.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _LimitsBase(BaseModel):
    """Common base. `extra="allow"` keeps non-canonical keys for
    forward-compat — losing extractor-discovered fields would be worse
    than carrying typed-but-unknown values."""

    model_config = ConfigDict(extra="allow")


# --- Resource-side categories ---------------------------------------------

class CloudLimits(_LimitsBase):
    """Always-free / free-tier cloud platforms (AWS, GCP, Azure, Oracle,
    Cloudflare, Render, Fly, etc.)."""

    compute_hours_per_month: int | None = Field(
        default=None,
        description="vCPU-hours included free per month, or 'always-free' instance hours like EC2 t2.micro 750h.",
    )
    vcpu: float | None = Field(default=None, description="vCPU count of the included instance class.")
    ram_gb: float | None = Field(default=None, description="RAM in GiB on the included instance class.")
    storage_gb: float | None = Field(default=None, description="Free block / disk storage in GiB.")
    bandwidth_gb: float | None = Field(default=None, description="Free egress bandwidth in GiB per month.")
    cold_start_seconds: float | None = Field(
        default=None,
        description="Approximate cold-start latency in seconds (Render free spin-down, Lambda first invoke).",
    )
    regions: list[str] | None = Field(default=None, description="Regions included in the free tier.")
    always_on: bool | None = Field(
        default=None,
        description="True = no idle spin-down. Drives the dashboard `personal` tier eligibility filter.",
    )
    custom_domain_supported: bool | None = None
    ssl_certificates: str | None = None
    commercial_use_allowed: bool | None = Field(
        default=None,
        description="False on Vercel Hobby — flagged so users don't hit ToS surprises post-launch.",
    )
    max_request_size_mb: float | None = None
    max_response_size_mb: float | None = None


class HostingLimits(CloudLimits):
    """Frontend / static-site hosting (Vercel, Netlify, Cloudflare Pages).
    Adds build-minute + preview-deploy keys on top of CloudLimits."""

    build_minutes_per_month: int | None = None
    serverless_invocations_per_day: int | None = None
    serverless_function_max_duration_s: int | None = None
    serverless_function_max_memory_mb: int | None = None
    edge_function_invocations_per_day: int | None = None
    preview_deployments: str | None = None
    image_optimizations_per_month: int | None = None


class GpuLimits(_LimitsBase):
    """GPU compute platforms (Colab, Kaggle, Lambda Labs, RunPod,
    Paperspace)."""

    gpu_model: str | None = None
    vram_gb: float | None = None
    hours_per_week: float | None = None
    max_session_hours: float | None = None
    concurrent_sessions: int | None = None
    preemptible: bool | None = None
    runtime_supported: list[str] | None = None
    idle_timeout_minutes: int | None = None
    regions: list[str] | None = None


class AiApiLimits(_LimitsBase):
    """LLM / vision / embedding / TTS / STT inference APIs (Groq, Gemini,
    Cerebras, OpenRouter, HuggingFace, Together, Mistral, etc.)."""

    models: list[str] | None = Field(default=None, description="Model IDs available on the free tier.")
    rpm: int | None = Field(default=None, description="Requests per minute.")
    rpd: int | None = Field(default=None, description="Requests per day.")
    tpm: int | None = Field(default=None, description="Tokens per minute.")
    tpd: int | None = Field(default=None, description="Tokens per day.")
    context_window: int | None = Field(default=None, description="Max input + output tokens per request.")
    vision_supported: bool | None = None
    function_calling_supported: bool | None = None
    structured_output_supported: bool | None = None
    audio_input_supported: bool | None = None
    audio_output_supported: bool | None = None
    embedding_supported: bool | None = None
    image_generation_supported: bool | None = None
    video_generation_supported: bool | None = None
    openai_compatible_api: bool | None = None
    free_quota_resets: str | None = Field(
        default=None,
        description="When does the quota reset? 'daily', 'monthly', 'rolling-30-days'.",
    )
    regions: list[str] | None = None
    data_used_for_training: str | None = None


class DatabaseLimits(_LimitsBase):
    """Managed databases — Postgres / MySQL / Mongo / Redis / vector
    (Supabase, Neon, PlanetScale, MongoDB Atlas, Upstash, Pinecone)."""

    database_size_mb: int | None = None
    database_engine: str | None = None
    row_limit: int | None = None
    connections: int | None = None
    branching_supported: bool | None = None
    point_in_time_recovery: str | None = None
    auto_pause_after_days_idle: int | None = None
    daily_backups_retention_days: int | None = None
    realtime_supported: bool | None = None
    vector_supported: bool | None = None
    read_replicas: int | None = None
    regions: list[str] | None = None


class StorageLimits(_LimitsBase):
    """Object / blob storage (R2, B2, S3-compatible free tiers)."""

    storage_gb: float | None = None
    egress_gb_per_month: float | None = None
    egress_fee: str | None = Field(
        default=None,
        description="'$0' for R2 (the killer feature); '$0.09/GB' for AWS, etc.",
    )
    operations_class_a: int | None = None
    operations_class_b: int | None = None
    api_compatibility: str | None = Field(default=None, description="e.g. 'S3-compatible'.")
    versioning: bool | None = None
    lifecycle_rules: bool | None = None
    presigned_urls: bool | None = None
    max_object_size_gb: float | None = None
    regions: list[str] | None = None


class AuthLimits(_LimitsBase):
    """Managed auth providers (Clerk, Auth0, Supabase Auth, Stytch)."""

    monthly_active_users: int | None = None
    social_providers: list[str] | None = None
    mfa_supported: bool | None = None
    sso_supported: bool | None = None
    custom_domain_supported: bool | None = None
    webhooks_supported: bool | None = None
    organizations_supported: bool | None = None
    seats: int | None = None


class ObservabilityLimits(_LimitsBase):
    """Logs / metrics / traces (Sentry, Grafana Cloud, Logflare, Axiom)."""

    events_per_month: int | None = None
    log_retention_days: int | None = None
    metrics_retention_days: int | None = None
    traces_supported: bool | None = None
    seats: int | None = None
    dashboards_count: int | None = None


class DomainLimits(_LimitsBase):
    """Domain registrars / DNS / email-routing (Cloudflare DNS, Namecheap)."""

    free_tlds: list[str] | None = None
    dns_records_max: int | None = None
    email_forwarding_supported: bool | None = None


class LearningLimits(_LimitsBase):
    """Free courses, certs, structured learning (Coursera audit, Kaggle Learn)."""

    course_count: int | None = None
    certificate_supported: bool | None = None
    cost_for_certificate_usd: float | None = None
    duration_hours: float | None = None


# --- Fund-side categories -------------------------------------------------

class GrantLimits(_LimitsBase):
    """Non-dilutive grants (Startup India, MeitY, NIH SBIR, Mozilla MOSS)."""

    grant_amount: float | None = None
    currency: str | None = None
    application_window: str | None = None
    decision_timeline_months: str | None = None
    sectors_priority: list[str] | None = None
    incubator_partner_required: bool | None = None
    milestones_required: bool | None = None
    tranches_typical: str | None = None
    reporting_required: str | None = None
    company_age_max_years: int | None = None
    indian_subsidiary_required: bool | None = None


class AcceleratorLimits(_LimitsBase):
    """Accelerator programs (YC, Techstars, NASSCOM 10000, Antler)."""

    investment_amount: float | None = None
    investment_structure: str | None = None
    equity_taken_percent: float | None = None
    batches_per_year: int | None = None
    batch_duration_weeks: int | None = None
    acceptance_rate_percent: float | None = None
    alumni_network_size: int | None = None
    alumni_perks_value_usd: float | None = None
    office_space: str | None = None
    remote_supported: bool | None = None
    demo_day_investors_attending: int | None = None


class StartupCreditLimits(_LimitsBase):
    """Cloud / SaaS credit programs (AWS Activate, GCP for Startups,
    Azure for Startups, Stripe Atlas)."""

    credit_amount_usd: float | None = None
    duration_months: int | None = None
    eligible_stages: list[str] | None = None
    eligible_age_max_years: int | None = None
    requires_investor_backing: bool | None = None
    services_eligible: list[str] | None = None
    support_included: str | None = None
    training_credits_usd: float | None = None
    regions: list[str] | None = None
    tiers: dict | None = Field(
        default=None,
        description="Per-tier breakdown for multi-tier programs (AWS Activate Founders / Portfolio / Enterprise).",
    )


class PerkLimits(_LimitsBase):
    """SaaS partner perks (Notion / Stripe / HubSpot for Startups, etc.)."""

    perk_value_usd: float | None = None
    discount_percent: float | None = None
    free_months: int | None = None
    eligible_user_types: list[str] | None = None
    partner_required: str | None = None
    activation_method: str | None = None
    expiry_months: int | None = None
    stacking_allowed: bool | None = None


class OssLimits(_LimitsBase):
    """Open-source artifacts (boilerplates, frameworks, model weights)."""

    stars: int | None = None
    license: str | None = None
    language: str | None = None
    last_commit_date: str | None = None
    demo_url: str | None = None
    self_hosted_only: bool | None = None


# --- Registry -------------------------------------------------------------

LIMITS_MODELS: dict[str, type[_LimitsBase]] = {
    # Resource-side
    "cloud": CloudLimits,
    "hosting": HostingLimits,
    "gpu": GpuLimits,
    "ai-api": AiApiLimits,
    "database": DatabaseLimits,
    "databases": DatabaseLimits,  # legacy plural
    "storage": StorageLimits,
    "auth": AuthLimits,
    "observability": ObservabilityLimits,
    "domain": DomainLimits,
    "domains": DomainLimits,  # legacy plural
    "learning": LearningLimits,
    "oss": OssLimits,
    # Fund-side (singular + legacy plural)
    "grant": GrantLimits,
    "grants": GrantLimits,
    "accelerator": AcceleratorLimits,
    "accelerators": AcceleratorLimits,
    "startup-credit": StartupCreditLimits,
    "startup-credits": StartupCreditLimits,
    "perk": PerkLimits,
    "perks": PerkLimits,
}


def validate_limits(category: str, raw: dict) -> dict:
    """Coerce a raw `limits` dict through the per-category typed model.

    - Canonical keys are coerced to their declared types (numeric strings
      → numbers; bool-like strings → bools; etc.).
    - Non-canonical keys pass through unchanged (`extra="allow"`).
    - Partial dicts are valid — any subset of canonical keys is fine.
    - Unknown category → pass-through (no model), so adding a new category
      doesn't break ingest before its `*Limits` class is defined.
    - `None` keys are excluded from the output via `exclude_none=True` so
      the DB column stays compact.

    Raises `pydantic.ValidationError` on coercion failure (e.g. canonical
    `compute_hours_per_month: int` field gets a non-numeric string that
    can't be coerced). The extractor catches this and decrements
    `parse_confidence` to `low` per `agentic-pipeline.md`.
    """
    if not isinstance(raw, dict):
        return raw  # pydantic will catch type error elsewhere
    Model = LIMITS_MODELS.get(category)
    if Model is None:
        return raw
    return Model.model_validate(raw).model_dump(exclude_none=True)
