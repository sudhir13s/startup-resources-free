"""MockBackend + OpenAICompatBackend + Backend selection tests.

Provider HTTP is the external boundary here — every OpenAICompatBackend
test mocks it with `httpx.MockTransport` rather than hitting a real
network. MockBackend itself is exercised directly (no network involved).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from freellm import Backend, get_backend, set_backend
from freellm.backends.mock import MockBackend
from freellm.backends.openai_compat import OpenAICompatBackend
from freellm.errors import (
    AuthError,
    ProviderRequestError,
    RateLimitedError,
    TransientProviderError,
)


def _backend_with_transport(handler) -> OpenAICompatBackend:
    """Build an OpenAICompatBackend whose httpx client is wired to `handler`."""
    backend = OpenAICompatBackend()
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return backend


# ---------- MockBackend ----------


def test_mock_backend_text_echoes_user_message():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_text_one(
            provider="groq",
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "hello world"}],
        )
    )
    assert result.provider_used == "groq"
    assert result.model_used == "openai/gpt-oss-120b"
    assert "hello world" in result.content
    assert result.cost_usd == 0.0


def test_mock_backend_text_pulls_text_from_multimodal_message():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_text_one(
            provider="gemini",
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "..."}},
                        {"type": "text", "text": "what's in this image"},
                    ],
                }
            ],
        )
    )
    assert "what's in this image" in result.content


def test_mock_backend_embed_returns_count_marker():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_embed_one(
            provider="voyage",
            model="voyage-3-lite",
            inputs=["a", "b", "c"],
        )
    )
    assert "count=3" in result.content
    assert result.provider_used == "voyage"


def test_mock_backend_fail_injection(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_FAIL_PROVIDERS", "groq")
    backend = MockBackend()
    with pytest.raises(RuntimeError, match="mock-fail: groq"):
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="x",
                messages=[{"role": "user", "content": "hi"}],
            )
        )


def test_mock_backend_satisfies_protocol():
    """Backend Protocol is runtime-checkable; MockBackend must conform."""
    assert isinstance(MockBackend(), Backend)


def test_mock_backend_json_mode_returns_json_shaped_content():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_text_one(
            provider="groq",
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "hello"}],
            response_format={"type": "json_object"},
        )
    )
    assert result.content.startswith("{")


# ---------- OpenAICompatBackend ----------


def test_openai_compat_text_success_parses_content_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello back"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    backend = _backend_with_transport(handler)
    result = asyncio.run(
        backend.call_text_one(
            provider="groq",
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "hi"}],
            api_key="test-key",
            base_url="https://api.groq.com/openai/v1",
        )
    )
    assert result.content == "hello back"
    assert result.tokens_in == 5
    assert result.tokens_out == 3
    assert result.cost_usd == 0.0


def test_openai_compat_json_mode_sends_response_format():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    backend = _backend_with_transport(handler)
    asyncio.run(
        backend.call_text_one(
            provider="groq",
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "give me json"}],
            api_key="k",
            base_url="https://api.groq.com/openai/v1",
            response_format={"type": "json_object"},
        )
    )
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_openai_compat_429_raises_rate_limited_with_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "12"}, text="rate limited")

    backend = _backend_with_transport(handler)
    with pytest.raises(RateLimitedError) as exc_info:
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                api_key="k",
                base_url="https://api.groq.com/openai/v1",
            )
        )
    assert exc_info.value.retry_after_s == 12.0
    assert exc_info.value.daily_exhausted is False


def test_openai_compat_429_detects_daily_exhaustion_from_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="daily quota exceeded, try again tomorrow")

    backend = _backend_with_transport(handler)
    with pytest.raises(RateLimitedError) as exc_info:
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                api_key="k",
                base_url="https://api.groq.com/openai/v1",
            )
        )
    assert exc_info.value.daily_exhausted is True


def test_openai_compat_401_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    backend = _backend_with_transport(handler)
    with pytest.raises(AuthError):
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                api_key="bad",
                base_url="https://api.groq.com/openai/v1",
            )
        )


def test_openai_compat_500_raises_transient_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    backend = _backend_with_transport(handler)
    with pytest.raises(TransientProviderError):
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                api_key="k",
                base_url="https://api.groq.com/openai/v1",
            )
        )


def test_openai_compat_other_4xx_raises_provider_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request shape")

    backend = _backend_with_transport(handler)
    with pytest.raises(ProviderRequestError):
        asyncio.run(
            backend.call_text_one(
                provider="groq",
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                api_key="k",
                base_url="https://api.groq.com/openai/v1",
            )
        )


def test_openai_compat_embed_parses_dim_and_count():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        return httpx.Response(
            200,
            json={
                "data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}],
                "usage": {"prompt_tokens": 4},
            },
        )

    backend = _backend_with_transport(handler)
    result = asyncio.run(
        backend.call_embed_one(
            provider="gemini",
            model="text-embedding-004",
            inputs=["a", "b"],
            api_key="k",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )
    )
    assert "count=2 dim=3" in result.content
    assert result.tokens_in == 4


def test_openai_compat_vision_reuses_text_route():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "a cat"}}]})

    backend = _backend_with_transport(handler)
    result = asyncio.run(
        backend.call_vision_one(
            provider="gemini",
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "x"}},
                        {"type": "text", "text": "describe"},
                    ],
                }
            ],
            api_key="k",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )
    )
    assert result.content == "a cat"


def test_openai_compat_satisfies_protocol():
    assert isinstance(OpenAICompatBackend(), Backend)


# ---------- get_backend / set_backend ----------


def test_get_backend_default_is_openai_compat(monkeypatch: pytest.MonkeyPatch):
    """Default backend kind is openai_compat. We don't make a network call
    here — we just confirm the env routing picks the right class.
    """
    set_backend(None)
    monkeypatch.delenv("FREELLM_BACKEND", raising=False)
    backend = get_backend()
    assert backend.name == "openai_compat"
    set_backend(None)


def test_set_backend_overrides_singleton():
    custom = MockBackend()
    set_backend(custom)
    try:
        assert get_backend() is custom
    finally:
        set_backend(None)


def test_get_backend_unknown_kind_raises(monkeypatch: pytest.MonkeyPatch):
    set_backend(None)
    monkeypatch.setenv("FREELLM_BACKEND", "totally-unknown")
    with pytest.raises(ValueError, match="Unknown FREELLM_BACKEND"):
        get_backend()
    set_backend(None)
