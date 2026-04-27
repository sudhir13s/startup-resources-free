"""Production backend — calls OmniRoute via its OpenAI-compatible API.

Lifecycle (managed via process-level singleton in `freellm.backend`):

1. First call: `_ensure_started()` runs `omni_route_config.bootstrap.ensure_running()`
   then `apply_config()` — idempotent, so a pre-running OmniRoute is detected
   and reused.
2. Subsequent calls: reuse the cached `AsyncOpenAI` client pointed at
   `OMNIROUTE_URL` (default `http://localhost:20128/api/v1`).
3. `aclose()` closes the OpenAI HTTP client; OmniRoute itself stays up
   (it's a separate process / container — `omni_route_config` owns its
   teardown via the `omniroutectl down` CLI).

Model addressing: OmniRoute uses LiteLLM under the hood and accepts
`provider/model` strings directly (e.g. `groq/llama-3.3-70b-versatile`).
The router passes both pieces; this backend joins them with `/`.

Dependencies (declared in `backend/requirements.txt`):
- `OmniRouteConfig` (git) — the lifecycle + config manager
- `openai` — the SDK we use to talk to OmniRoute's OpenAI-compat routes

Failure modes propagate as exceptions; the router catches and walks the
chain, recording each failure in quotas.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from freellm.schemas import Result

if TYPE_CHECKING:
    from openai import AsyncOpenAI


class OmniRouteBackend:
    name = "omniroute"

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._started: bool = False

    async def _ensure_started(self) -> None:
        if self._started and self._client is not None:
            return

        try:
            from omni_route_config import bootstrap
        except ImportError as e:
            raise ImportError(
                "OmniRouteBackend requires the OmniRouteConfig package. "
                "Install the agent stack: "
                "`pip install -r backend/requirements-agents.txt`. "
                "Or set FREELLM_BACKEND=mock for offline / CI use."
            ) from e

        # Honor a pre-set OMNIROUTE_URL — keeps tests + alt deployments
        # easy to reroute without touching this code.
        if os.environ.get("FREELLM_OMNIROUTE_AUTOSTART", "1") == "1":
            await bootstrap.ensure_running()
            await bootstrap.apply_config()
        # else: trust the operator — caller pre-started OmniRoute.

        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "OmniRouteBackend requires the `openai` package. "
                "Install the agent stack: "
                "`pip install -r backend/requirements-agents.txt`."
            ) from e

        base = os.environ.get("OMNIROUTE_URL", "http://localhost:20128").rstrip("/")
        api_key = (
            os.environ.get("OMNIROUTE_API_TOKEN", "").strip()
            or "sk-omniroute-local"
        )
        self._client = AsyncOpenAI(base_url=f"{base}/api/v1", api_key=api_key)
        self._started = True

    @staticmethod
    def _model_id(provider: str, model: str) -> str:
        # OmniRoute / LiteLLM canonical id: "<provider>/<model>".
        # Some catalog rows already include a slash (e.g.
        # "meta-llama/Meta-Llama-3-8B-Instruct"); guard against duplication.
        if model.startswith(f"{provider}/"):
            return model
        return f"{provider}/{model}"

    async def call_text_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
    ) -> Result:
        await self._ensure_started()
        assert self._client is not None
        t0 = time.monotonic()
        resp = await self._client.chat.completions.create(
            model=self._model_id(provider, model),
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout_s,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = getattr(resp, "usage", None)
        return Result(
            content=content,
            provider_used=provider,
            model_used=model,
            latency_ms=latency_ms,
            cost_usd=0.0,
            tokens_in=getattr(usage, "prompt_tokens", None),
            tokens_out=getattr(usage, "completion_tokens", None),
        )

    async def call_vision_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
    ) -> Result:
        # Vision flows through chat/completions in the OpenAI-compat shape:
        # the caller embeds image_url parts in `messages`. Same transport.
        return await self.call_text_one(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    async def call_embed_one(
        self,
        *,
        provider: str,
        model: str,
        inputs: list[str],
        timeout_s: int = 60,
    ) -> Result:
        await self._ensure_started()
        assert self._client is not None
        t0 = time.monotonic()
        resp = await self._client.embeddings.create(
            model=self._model_id(provider, model),
            input=inputs,
            timeout=timeout_s,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        # Surface dim + count so callers can sanity-check without parsing
        # the full vector from `content`. The vector itself is in resp.data.
        first_dim = len(resp.data[0].embedding) if resp.data else 0
        usage = getattr(resp, "usage", None)
        return Result(
            content=f"embeddings count={len(resp.data)} dim={first_dim}",
            provider_used=provider,
            model_used=model,
            latency_ms=latency_ms,
            cost_usd=0.0,
            tokens_in=getattr(usage, "prompt_tokens", None),
            tokens_out=0,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._client = None
        self._started = False
