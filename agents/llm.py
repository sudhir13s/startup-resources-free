"""Structured-output wrapper around `freellm.call_text`.

Every extraction-style agent call goes through `call_structured(...)`.
It:

1. Loads the prompt template from `agents/prompts/<name>.md`.
2. Builds the OpenAI-style chat messages.
3. Calls `freellm.call_text(...)` (which walks the OmniRoute chain).
4. Parses the model output into the caller's Pydantic model.
5. Returns `(model_instance, raw_text, parse_confidence)`.

`parse_confidence` heuristic:
- `high`   — JSON parses cleanly, all required fields present, no nulls
            in required slots.
- `medium` — JSON parses, but some optional fields are null OR the model
            wrapped the JSON in markdown fences we had to strip.
- `low`    — JSON parse failed; we returned a best-effort partial OR
            the caller should send the record to `verifier.queue_low_confidence`.

The wrapper never raises on parse failure. Returning `low` is the
expected branch — agents handle it explicitly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

import freellm
from schema.records import ParseConfidence

if TYPE_CHECKING:
    from freellm import Backend


T = TypeVar("T", bound=BaseModel)


_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class StructuredResult:
    """What `call_structured` returns."""

    parsed: BaseModel | None
    raw_text: str
    parse_confidence: ParseConfidence
    provider_used: str
    model_used: str
    chain_attempted: list[str]
    error: str | None = None


def load_prompt(name: str) -> str:
    """Read `agents/prompts/<name>.md`.

    The YAML front-matter is preserved verbatim — it costs ~30 tokens
    per call and serves two roles: (1) version-pin the prompt body so
    auditing past LLM behavior stays straightforward, (2) gives test
    backends a stable key (the `agent:` line) to script responses by.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt {name!r} not found at {path}")
    return path.read_text(encoding="utf-8")


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_fence(text: str) -> tuple[str, bool]:
    """Strip a single ```json ... ``` fence. Returns (cleaned, was_fenced)."""
    m = _FENCE_RE.match(text.strip())
    if m:
        return m.group(1), True
    return text, False


async def call_structured(
    *,
    prompt_name: str,
    user_input: str,
    response_model: type[T],
    task_name: str,
    backend: "Backend | None" = None,
    max_tokens: int = 2000,
    temperature: float = 0.0,
    persist_quotas: bool = True,
) -> StructuredResult:
    """Call freellm.call_text with the named prompt and parse the JSON
    response into `response_model`.

    The system prompt is loaded from `agents/prompts/<prompt_name>.md`.
    The user message is `user_input` verbatim (caller already pre-formats
    HTML / context). Models are instructed in the prompt to emit JSON;
    we strip a single ```json fence if the model wraps its output.
    """
    system_prompt = load_prompt(prompt_name)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    result = await freellm.call_text(
        messages=messages,
        task_name=task_name,
        max_tokens=max_tokens,
        temperature=temperature,
        backend=backend,
        persist_quotas=persist_quotas,
    )
    raw = result.content  # type: ignore[union-attr]
    cleaned, was_fenced = _strip_fence(raw)

    parsed: BaseModel | None
    confidence: ParseConfidence
    error: str | None = None
    try:
        payload: Any = json.loads(cleaned)
        parsed = response_model.model_validate(payload)
        confidence = "medium" if was_fenced else "high"
        # Demote to medium if any optional field came back null (heuristic
        # — a model that admits "I don't know" is less confident than
        # one that filled every slot). We approximate by checking the
        # round-trip dict for null values.
        as_dict = parsed.model_dump()
        if any(v is None for v in as_dict.values()):
            confidence = "medium"
    except json.JSONDecodeError as e:
        parsed = None
        confidence = "low"
        error = f"json: {e}"
    except ValidationError as e:
        parsed = None
        confidence = "low"
        error = f"schema: {e.error_count()} validation errors"

    return StructuredResult(
        parsed=parsed,
        raw_text=raw,
        parse_confidence=confidence,
        provider_used=result.provider_used,  # type: ignore[union-attr]
        model_used=result.model_used,  # type: ignore[union-attr]
        chain_attempted=list(result.chain_attempted),  # type: ignore[union-attr]
        error=error,
    )
