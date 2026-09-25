"""LLM extraction: current record (or none) + page text -> ProviderRecord.

Calls `freellm.call_text(json_mode=True, temperature=0)` with the versioned
prompt in `refresh/prompts/extract.md`. Validates the response against
`ProviderRecord`; on a `ValidationError` retries once with the errors
appended to the user message, then gives up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

import freellm
from domain.records import ProviderRecord

_PROMPT_PATH = Path(__file__).parent / "prompts" / "extract.md"
MAX_INPUT_CHARS = 20_000


class ExtractionFailedError(RuntimeError):
    """Raised when the LLM's output never validates as a ProviderRecord."""


@dataclass
class ExtractionResult:
    """A successfully validated extraction plus which LLM answered."""

    record: ProviderRecord
    provider_used: str
    model_used: str


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _user_message(current: ProviderRecord | None, page_text: str) -> str:
    current_json = json.dumps(current.to_storage(), sort_keys=True) if current else "null"
    truncated = page_text[:MAX_INPUT_CHARS]
    return f"CURRENT_RECORD:\n{current_json}\n\nPAGE_TEXT:\n{truncated}"


def _parse_json_object(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionFailedError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExtractionFailedError("LLM response JSON was not an object")
    return payload


async def extract_record(
    *,
    current: ProviderRecord | None,
    page_text: str,
    task_name: str,
) -> ExtractionResult:
    """Extract the full ProviderRecord for one provider's page(s).

    Validation failures retry ONCE with the Pydantic error list appended
    to the user message, asking the model to correct its own output.
    `AllProvidersExhaustedError` from `freellm` propagates to the caller
    (`runner.py`), which treats it as the free-LLM budget being spent.
    """
    system_prompt = _load_prompt()
    user_message = _user_message(current, page_text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    result = await freellm.call_text(
        messages=messages, task_name=task_name, temperature=0, json_mode=True
    )
    payload = _parse_json_object(result.content)
    try:
        record = ProviderRecord.model_validate(payload)
    except ValidationError as first_error:
        record = await _retry_with_errors(
            messages=messages, task_name=task_name, errors=first_error
        )
        return ExtractionResult(
            record=record, provider_used=result.provider_used, model_used=result.model_used
        )
    return ExtractionResult(
        record=record, provider_used=result.provider_used, model_used=result.model_used
    )


async def _retry_with_errors(
    *, messages: list[dict], task_name: str, errors: ValidationError
) -> ProviderRecord:
    retry_messages = [
        *messages,
        {
            "role": "user",
            "content": (
                "Your previous JSON failed validation with these errors. "
                "Return a corrected, complete JSON object only:\n"
                f"{errors}"
            ),
        },
    ]
    result = await freellm.call_text(
        messages=retry_messages, task_name=task_name, temperature=0, json_mode=True
    )
    payload = _parse_json_object(result.content)
    try:
        return ProviderRecord.model_validate(payload)
    except ValidationError as second_error:
        raise ExtractionFailedError(
            f"validation failed twice: {second_error.error_count()} errors"
        ) from second_error
