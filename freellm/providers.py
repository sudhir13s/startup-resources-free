"""Canonical free-tier provider catalog.

Source of truth for "what free LLMs / multimodal endpoints we route through,"
AND for the OpenAI-compatible transport details (`base_url`, `env_var`) that
`freellm/backends/openai_compat.py` uses to make the call. Curated manually;
the agent pipeline can SUGGEST updates via PR but never auto-merges. See
`.claude/rules/project/freellm-router.md` for the policy.

Verify monthly — providers shift free tiers quarterly. Entries with
`last_verified` older than ~60 days should be re-checked against
`docs_url` before being trusted for a production run.
"""

from __future__ import annotations

from datetime import date

from freellm.schemas import (
    AlwaysFreeWithLimits,
    Modality,
    OneTimeCredits,
    ProviderEntry,
    RequestsPerDay,
    RpmRpd,
)

LAST_CATALOG_REVIEW = date(2026, 9, 25)

# OpenAI-compatible base URLs, one per provider slug. `ProviderEntry.base_url`
# always points here so the URL lives in exactly one place per provider.
BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
    "huggingface": "https://router.huggingface.co/v1",
}

# Providers not on the OpenAI-compat transport (image/video/embed-only
# vendors kept from the pre-existing catalog). Their base_url is informational
# only — call_image_gen / call_video_gen remain unimplemented until v0.3.
_NON_CHAT_BASE_URLS: dict[str, str] = {
    "replicate": "https://api.replicate.com/v1",
    "fal_ai": "https://fal.run",
    "voyage": "https://api.voyageai.com/v1",
    "cohere": "https://api.cohere.com/v1",
    "elevenlabs": "https://api.elevenlabs.io/v1",
}


def _base_url(provider: str) -> str:
    if provider in BASE_URLS:
        return BASE_URLS[provider]
    return _NON_CHAT_BASE_URLS[provider]


# Convenience constructors keep the catalog rows compact.
def _rpm_rpd(rpm: int | None = None, rpd: int | None = None, **kw: object) -> RpmRpd:
    return RpmRpd(rpm=rpm, rpd=rpd, **kw)  # type: ignore[arg-type]


def _rpd(rpd: int, **kw: object) -> RequestsPerDay:
    return RequestsPerDay(rpd=rpd, **kw)  # type: ignore[arg-type]


def _credits(usd: float, **kw: object) -> OneTimeCredits:
    return OneTimeCredits(usd=usd, **kw)  # type: ignore[arg-type]


def _free_with_limits(notes: str) -> AlwaysFreeWithLimits:
    return AlwaysFreeWithLimits(notes=notes)


PROVIDERS: dict[Modality, list[ProviderEntry]] = {
    # ============================================================
    # text — chat / completion
    # The router tries entries top to bottom, so order = free daily
    # headroom: Groq and Gemini (1000-1500/day each) cover a full
    # refresh; Cerebras is the large backup; small or unverified pools
    # follow.
    # ============================================================
    "text": [
        ProviderEntry(
            provider="groq",
            model="openai/gpt-oss-120b",
            free_tier=_rpm_rpd(rpm=30, rpd=1000),
            env_var="GROQ_API_KEY",
            base_url=_base_url("groq"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://console.groq.com/docs/rate-limits",
            notes=(
                "Largest model on Groq's current free tier. "
                "llama-3.3-70b-versatile dropped off the public free table "
                "(now enterprise-only) — replaced 2026-09-25."
            ),
        ),
        ProviderEntry(
            provider="groq",
            model="openai/gpt-oss-20b",
            free_tier=_rpm_rpd(rpm=30, rpd=1000),
            env_var="GROQ_API_KEY",
            base_url=_base_url("groq"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://console.groq.com/docs/rate-limits",
            notes="Cheaper/faster Groq fallback within the same free pool.",
        ),
        ProviderEntry(
            provider="gemini",
            model="gemini-2.5-flash",
            free_tier=_rpd(rpd=1500),
            env_var="GEMINI_API_KEY",
            base_url=_base_url("gemini"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://ai.google.dev/gemini-api/docs/openai",
            notes=(
                "OpenAI-compat endpoint confirmed at "
                "generativelanguage.googleapis.com/v1beta/openai. Free-tier "
                "RPD not machine-verified this pass — recheck AI Studio "
                "before relying on the 1500/day figure."
            ),
        ),
        ProviderEntry(
            provider="cerebras",
            model="llama3.1-70b",
            free_tier=_rpd(rpd=14400),
            env_var="CEREBRAS_API_KEY_19S",
            base_url=_base_url("cerebras"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://inference-docs.cerebras.ai/introduction",
            notes=(
                "OpenAI-compat base URL confirmed (api.cerebras.ai/v1). "
                "Free-tier RPD carried over from prior verification — "
                "Cerebras docs don't publish a machine-readable free-tier "
                "table; recheck cloud.cerebras.ai before relying on it."
            ),
        ),
        ProviderEntry(
            provider="mistral",
            model="open-mistral-7b",
            free_tier=_free_with_limits("Free tier rate-limited. Phone OTP signup."),
            env_var="MISTRAL_API_KEY",
            base_url=_base_url("mistral"),
            speed_tier="medium",
            last_verified=date(2026, 4, 21),
            docs_url="https://docs.mistral.ai/",
            notes="Not re-verified 2026-09-25 (docs page moved, 404 on fetch); recheck.",
        ),
        ProviderEntry(
            provider="nvidia_nim",
            model="meta/llama-3.1-8b-instruct",
            free_tier=_free_with_limits("Free NIM API credits for evaluation use."),
            env_var="NVIDIA_API_KEY_19S",
            base_url=_base_url("nvidia_nim"),
            speed_tier="medium",
            last_verified=date(2026, 4, 21),
            docs_url="https://build.nvidia.com/",
            notes="Not re-verified 2026-09-25 — recheck credit terms before relying on it.",
        ),
        ProviderEntry(
            provider="openrouter",
            model="meta-llama/llama-3.1-70b-instruct:free",
            free_tier=_free_with_limits(
                "20 RPM; 50 RPD (<10 credits purchased) or 1000 RPD (10+ credits)."
            ),
            env_var="OPENROUTER_API_KEY_19S",
            base_url=_base_url("openrouter"),
            speed_tier="medium",
            last_verified=date(2026, 9, 25),
            docs_url="https://openrouter.ai/docs/api-reference/limits",
            notes="Free-model rate limits confirmed via OpenRouter docs.",
        ),
        ProviderEntry(
            provider="openrouter",
            model="google/gemini-flash-1.5:free",
            free_tier=_free_with_limits(
                "20 RPM; 50 RPD (<10 credits purchased) or 1000 RPD (10+ credits)."
            ),
            env_var="OPENROUTER_API_KEY_19S",
            base_url=_base_url("openrouter"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://openrouter.ai/docs/api-reference/limits",
        ),
        ProviderEntry(
            provider="huggingface",
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            free_tier=_free_with_limits("HF Router; shared free pool."),
            env_var="HF_TOKEN",
            base_url=_base_url("huggingface"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
            docs_url="https://huggingface.co/docs/inference-providers/index",
            notes="Not re-verified 2026-09-25 — recheck before relying on it.",
        ),
    ],
    # ============================================================
    # vision — text + image input -> text output
    # ============================================================
    "vision": [
        ProviderEntry(
            provider="gemini",
            model="gemini-2.5-flash",
            free_tier=_rpd(rpd=1500),
            env_var="GEMINI_API_KEY",
            base_url=_base_url("gemini"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://ai.google.dev/gemini-api/docs/openai",
        ),
        ProviderEntry(
            provider="openrouter",
            model="meta-llama/llama-3.2-11b-vision-instruct:free",
            free_tier=_free_with_limits("Free :free vision via OpenRouter."),
            env_var="OPENROUTER_API_KEY_19S",
            base_url=_base_url("openrouter"),
            speed_tier="medium",
            last_verified=date(2026, 9, 25),
            docs_url="https://openrouter.ai/docs/api-reference/limits",
        ),
    ],
    # ============================================================
    # image_gen — dry-run only until v0.3 (Media Benchmark)
    # ============================================================
    "image_gen": [
        ProviderEntry(
            provider="huggingface",
            model="black-forest-labs/FLUX.1-schnell",
            free_tier=_free_with_limits("HF Router free; shared pool."),
            env_var="HF_TOKEN",
            base_url=_base_url("huggingface"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
        ProviderEntry(
            provider="replicate",
            model="black-forest-labs/flux-schnell",
            free_tier=_credits(1.0, notes="Small monthly free compute."),
            env_var="REPLICATE_API_TOKEN",
            base_url=_base_url("replicate"),
            speed_tier="medium",
            last_verified=date(2026, 4, 19),
        ),
        ProviderEntry(
            provider="fal_ai",
            model="fal-ai/flux/schnell",
            free_tier=_credits(1.0, notes="Signup credits + free quota on fast models."),
            env_var="FAL_API_KEY",
            base_url=_base_url("fal_ai"),
            speed_tier="fast",
            last_verified=date(2026, 4, 19),
        ),
    ],
    # ============================================================
    # video_gen — dry-run only until v0.3
    # ============================================================
    "video_gen": [
        ProviderEntry(
            provider="replicate",
            model="stability-ai/stable-video-diffusion",
            free_tier=_credits(1.0, notes="Limited free quota."),
            env_var="REPLICATE_API_TOKEN",
            base_url=_base_url("replicate"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
        ProviderEntry(
            provider="fal_ai",
            model="fal-ai/animatediff-v2v",
            free_tier=_credits(1.0, notes="Limited free quota."),
            env_var="FAL_API_KEY",
            base_url=_base_url("fal_ai"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
    ],
    # ============================================================
    # embed
    # ============================================================
    "embed": [
        ProviderEntry(
            provider="gemini",
            model="text-embedding-004",
            free_tier=_rpd(rpd=1500),
            env_var="GEMINI_API_KEY",
            base_url=_base_url("gemini"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://ai.google.dev/gemini-api/docs/openai",
        ),
        ProviderEntry(
            provider="voyage",
            model="voyage-3-lite",
            free_tier=AlwaysFreeWithLimits(notes="50M tokens lifetime free."),
            env_var="VOYAGE_API_KEY",
            base_url=_base_url("voyage"),
            speed_tier="fast",
            last_verified=date(2026, 4, 18),
            docs_url="https://docs.voyageai.com/docs/pricing",
        ),
        ProviderEntry(
            provider="cohere",
            model="embed-english-v3.0",
            free_tier=_free_with_limits("Trial key; rate-limited."),
            env_var="COHERE_API_KEY",
            base_url=_base_url("cohere"),
            speed_tier="fast",
            last_verified=date(2026, 4, 18),
        ),
        ProviderEntry(
            provider="mistral",
            model="mistral-embed",
            free_tier=_free_with_limits("Free tier rate-limited."),
            env_var="MISTRAL_API_KEY",
            base_url=_base_url("mistral"),
            speed_tier="fast",
            last_verified=date(2026, 4, 21),
        ),
        ProviderEntry(
            provider="huggingface",
            model="sentence-transformers/all-MiniLM-L6-v2",
            free_tier=_free_with_limits("HF Router free."),
            env_var="HF_TOKEN",
            base_url=_base_url("huggingface"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
    ],
    # ============================================================
    # stt — speech to text — dry-run only until v0.3
    # ============================================================
    "stt": [
        ProviderEntry(
            provider="groq",
            model="whisper-large-v3",
            free_tier=_rpm_rpd(rpm=20, rpd=2000),
            env_var="GROQ_API_KEY",
            base_url=_base_url("groq"),
            speed_tier="fast",
            last_verified=date(2026, 9, 25),
            docs_url="https://console.groq.com/docs/rate-limits",
        ),
        ProviderEntry(
            provider="huggingface",
            model="openai/whisper-large-v3",
            free_tier=_free_with_limits("HF Router free; shared pool."),
            env_var="HF_TOKEN",
            base_url=_base_url("huggingface"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
    ],
    # ============================================================
    # tts — dry-run only until v0.3
    # ============================================================
    "tts": [
        ProviderEntry(
            provider="huggingface",
            model="suno/bark",
            free_tier=_free_with_limits("HF Router free."),
            env_var="HF_TOKEN",
            base_url=_base_url("huggingface"),
            speed_tier="slow",
            last_verified=date(2026, 4, 19),
        ),
        ProviderEntry(
            provider="elevenlabs",
            model="eleven_turbo_v2_5",
            free_tier=AlwaysFreeWithLimits(notes="10,000 chars/month free."),
            env_var="ELEVENLABS_API_KEY",
            base_url=_base_url("elevenlabs"),
            speed_tier="fast",
            last_verified=date(2026, 4, 19),
            docs_url="https://elevenlabs.io/pricing",
        ),
    ],
}


def list_providers(modality: Modality | None = None) -> list[ProviderEntry]:
    """Return catalog rows. If `modality` is None, returns all rows across modalities."""
    if modality is not None:
        return list(PROVIDERS.get(modality, []))
    out: list[ProviderEntry] = []
    for entries in PROVIDERS.values():
        out.extend(entries)
    return out
