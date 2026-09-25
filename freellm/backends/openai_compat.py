"""Production backend — plain async httpx against OpenAI-compatible APIs.

No SDK, no sidecar process: every provider in the catalog exposes an
OpenAI-compatible `/chat/completions` (and often `/embeddings`) route, so
one small httpx client covers Groq, Gemini, OpenRouter, Cerebras, Mistral,
SambaNova, NVIDIA NIM, Together, HF Router, and GitHub Models. This fits a
512 MB Render free web service — no Node sidecar, no heavy SDK footprint.

Each `ProviderEntry` in `providers.py` carries its own `base_url` and
`env_var`; this backend just joins `base_url + "/chat/completions"` and
sends the standard OpenAI request body. Vision messages use the same route
(callers embed `image_url` parts in `messages`); embeddings use
`/embeddings`.

Failure mapping (see `freellm/errors.py`):
- 429                -> RateLimitedError (retry_after_s from `Retry-After`
                        header when present; daily_exhausted heuristic from
                        response body / header hints)
- 408 / 5xx / network -> TransientProviderError
- 401 / 403          -> AuthError
- other 4xx          -> ProviderRequestError
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from freellm.errors import (
    AuthError,
    ProviderRequestError,
    RateLimitedError,
    TransientProviderError,
)
from freellm.schemas import Result

_DEFAULT_TIMEOUT_S = 60


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Read `Retry-After` (seconds or HTTP-date) or provider-specific hints."""
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None  # HTTP-date form — uncommon on these APIs, skip parsing


def _looks_daily_exhausted(response: httpx.Response) -> bool:
    """Heuristic: providers signal a DAY cap (vs. a short RPM cap) in the
    response body text ("daily", "per day", "RPD") rather than a distinct
    status code. Absent a machine-readable field, this text check is the
    only signal available across all ten providers.
    """
    body = response.text.lower()
    return "daily" in body or "per day" in body or "rpd" in body


def _raise_for_status(provider: str, response: httpx.Response) -> None:
    if response.is_success:
        return
    status = response.status_code
    if status == 429:
        raise RateLimitedError(
            provider,
            f"rate limited (HTTP 429): {response.text[:200]}",
            retry_after_s=_parse_retry_after(response),
            daily_exhausted=_looks_daily_exhausted(response),
        )
    if status in (401, 403):
        raise AuthError(provider, f"auth rejected (HTTP {status}): {response.text[:200]}")
    if status == 408 or status >= 500:
        raise TransientProviderError(
            provider, f"transient failure (HTTP {status}): {response.text[:200]}"
        )
    raise ProviderRequestError(provider, f"HTTP {status}: {response.text[:200]}")


class OpenAICompatBackend:
    """Executes one provider call via its OpenAI-compatible HTTP API."""

    name = "openai_compat"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def call_text_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        api_key: str,
        base_url: str,
        response_format: dict[str, str] | None = None,
    ) -> Result:
        client = self._ensure_client()
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format
        t0 = time.monotonic()
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
        )
        _raise_for_status(provider, response)
        latency_ms = int((time.monotonic() - t0) * 1000)
        payload = response.json()
        choice = payload["choices"][0]
        content = choice["message"].get("content") or ""
        usage = payload.get("usage") or {}
        return Result(
            content=content,
            provider_used=provider,
            model_used=model,
            latency_ms=latency_ms,
            cost_usd=0.0,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )

    async def call_vision_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        api_key: str,
        base_url: str,
    ) -> Result:
        # Vision flows through the same chat/completions route — the caller
        # embeds `image_url` content parts in `messages`.
        return await self.call_text_one(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
            api_key=api_key,
            base_url=base_url,
        )

    async def call_embed_one(
        self,
        *,
        provider: str,
        model: str,
        inputs: list[str],
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        api_key: str,
        base_url: str,
    ) -> Result:
        client = self._ensure_client()
        t0 = time.monotonic()
        response = await client.post(
            f"{base_url.rstrip('/')}/embeddings",
            json={"model": model, "input": inputs},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
        )
        _raise_for_status(provider, response)
        latency_ms = int((time.monotonic() - t0) * 1000)
        payload = response.json()
        data = payload.get("data", [])
        first_dim = len(data[0]["embedding"]) if data else 0
        usage = payload.get("usage") or {}
        return Result(
            content=f"embeddings count={len(data)} dim={first_dim}",
            provider_used=provider,
            model_used=model,
            latency_ms=latency_ms,
            cost_usd=0.0,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=0,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None
