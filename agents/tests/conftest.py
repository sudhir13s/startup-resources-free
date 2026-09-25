"""Shared fixtures for agent tests.

`scripted_backend` factory returns a MockBackend subclass that returns
caller-supplied JSON strings keyed by `task_name`. Lets each test seed
exactly the LLM payload it expects to parse.
"""

from __future__ import annotations

from typing import Any

import pytest

from freellm.backends.mock import MockBackend


class ScriptedBackend(MockBackend):
    """MockBackend whose call_text_one returns scripted content."""

    name = "scripted"

    def __init__(self) -> None:
        super().__init__()
        # task_name -> response content. If task_name is missing, falls
        # back to the parent MockBackend's echo behavior.
        self.responses: dict[str, str] = {}
        # Tracks every (task_name, provider, model) tuple invoked.
        self.calls: list[tuple[str, str, str]] = []

    def script(self, task_name: str, content: str) -> None:
        self.responses[task_name] = content

    async def call_text_one(  # type: ignore[override]
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
        **_transport: Any,  # api_key / base_url / response_format — unused by the script
    ):
        self._maybe_fail(provider)
        # We tag the task via the user message content for visibility,
        # but the lookup key is supplied at the wrapper layer (we patch
        # the task_name into the messages from outside).
        # The agents.llm wrapper preserves the original `task_name`
        # by passing it to freellm.call_text -> backend; we surface
        # it via a custom message marker.
        task = self._sniff_task(messages)
        self.calls.append((task, provider, model))
        if task in self.responses:
            content = self.responses[task]
        else:
            content = self._last_user_text(messages)
        from freellm.schemas import Result

        return Result(
            content=content,
            provider_used=provider,
            model_used=model,
            latency_ms=1,
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
        )

    @staticmethod
    def _sniff_task(messages: list[dict[str, Any]]) -> str:
        # The system prompt's first line carries the agent name in our
        # YAML front-matter. ScriptedBackend uses that as the lookup key.
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content", "")
                if isinstance(content, str):
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("agent:"):
                            return line.split(":", 1)[1].strip()
                        if line and not line.startswith("---"):
                            break
        return "unknown"


@pytest.fixture
def scripted_backend() -> ScriptedBackend:
    return ScriptedBackend()


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch: pytest.MonkeyPatch):
    """Most agent tests need at least one provider key so the chain runs."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    yield


@pytest.fixture(autouse=True)
def _isolate_quotas(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path))
    yield


@pytest.fixture(autouse=True)
def _isolate_verify_queue(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERIFY_QUEUE_DIR", str(tmp_path / "verify"))
    yield
