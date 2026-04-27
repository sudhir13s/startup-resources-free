"""Deterministic in-process backend for tests + smoke runs.

No network, no LLM. Returns a canned Result whose `content` echoes the
last user message (text/vision) or a placeholder embedding marker.

Useful in two places:
1. CI tests — exercise router chain logic without spinning OmniRoute.
2. Local dev offline — run agents end-to-end against canned output.

Failure injection: set `MOCK_FAIL_PROVIDERS=groq,gemini` to make those
providers raise `RuntimeError("mock-fail")`. Router records the failure
and falls through.
"""

from __future__ import annotations

import os
from typing import Any

from freellm.schemas import Result


class MockBackend:
    name = "mock"

    def _fail_set(self) -> set[str]:
        raw = os.environ.get("MOCK_FAIL_PROVIDERS", "").strip()
        return {p.strip() for p in raw.split(",") if p.strip()}

    def _maybe_fail(self, provider: str) -> None:
        if provider in self._fail_set():
            raise RuntimeError(f"mock-fail: {provider}")

    @staticmethod
    def _last_user_text(messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            return str(part.get("text", ""))
        return ""

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
        self._maybe_fail(provider)
        echo = self._last_user_text(messages)
        return Result(
            content=f"[mock:{provider}/{model}] {echo}",
            provider_used=provider,
            model_used=model,
            latency_ms=1,
            cost_usd=0.0,
            tokens_in=len(echo.split()),
            tokens_out=8,
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
        self._maybe_fail(provider)
        echo = self._last_user_text(messages)
        return Result(
            content=f"[mock-vision:{provider}/{model}] {echo or '(image-only)'}",
            provider_used=provider,
            model_used=model,
            latency_ms=2,
            cost_usd=0.0,
            tokens_in=len(echo.split()),
            tokens_out=12,
        )

    async def call_embed_one(
        self,
        *,
        provider: str,
        model: str,
        inputs: list[str],
        timeout_s: int = 60,
    ) -> Result:
        self._maybe_fail(provider)
        # Embedding "content" is a JSON-serializable hint, not the vector.
        # Real backend stores the vector elsewhere; mock returns a marker.
        return Result(
            content=f"[mock-embed:{provider}/{model}] count={len(inputs)}",
            provider_used=provider,
            model_used=model,
            latency_ms=1,
            cost_usd=0.0,
            tokens_in=sum(len(i.split()) for i in inputs),
            tokens_out=0,
        )

    async def aclose(self) -> None:
        return None
