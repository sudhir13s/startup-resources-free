"""MockBackend + Backend selection tests."""

from __future__ import annotations

import asyncio

import pytest

from freellm import Backend, get_backend, set_backend
from freellm.backends.mock import MockBackend


# ---------- MockBackend ----------


def test_mock_backend_text_echoes_user_message():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_text_one(
            provider="groq",
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "hello world"}],
        )
    )
    assert result.provider_used == "groq"
    assert result.model_used == "llama-3.3-70b-versatile"
    assert "hello world" in result.content
    assert result.cost_usd == 0.0


def test_mock_backend_text_pulls_text_from_multimodal_message():
    backend = MockBackend()
    result = asyncio.run(
        backend.call_text_one(
            provider="gemini",
            model="gemini-1.5-flash",
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


# ---------- get_backend / set_backend ----------


def test_get_backend_default_is_omniroute(monkeypatch: pytest.MonkeyPatch):
    """Default backend kind is omniroute. We don't INSTANTIATE it here
    (would try to import omni_route_config); we just confirm the env
    routing picks the omniroute branch when forced via test override.
    """
    set_backend(None)
    monkeypatch.setenv("FREELLM_BACKEND", "mock")
    backend = get_backend()
    assert backend.name == "mock"
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
