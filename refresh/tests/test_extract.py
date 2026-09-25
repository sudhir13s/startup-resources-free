from __future__ import annotations

import asyncio

import pytest

import freellm
from freellm import AllProvidersExhaustedError
from refresh.extract import ExtractionFailedError, extract_record
from refresh.tests.conftest import ScriptedBackend, extracted_json


def test_should_return_validated_record_when_llm_returns_clean_json(all_llm_keys_present):
    backend = ScriptedBackend([extracted_json()])
    freellm.set_backend(backend)

    result = asyncio.run(
        extract_record(current=None, page_text="Groq free tier page text", task_name="test")
    )

    assert result.record.provider_id == "groq"
    assert result.provider_used  # the catalog provider that answered, e.g. "groq"


def test_should_retry_once_when_validation_fails_then_succeed(all_llm_keys_present):
    backend = ScriptedBackend(
        [
            '{"provider_id": "groq"}',  # missing required fields -> ValidationError
            extracted_json(),
        ]
    )
    freellm.set_backend(backend)

    result = asyncio.run(
        extract_record(current=None, page_text="page text", task_name="test")
    )

    assert result.record.provider_id == "groq"
    assert len(backend.calls) == 2


def test_should_raise_when_validation_fails_twice(all_llm_keys_present):
    backend = ScriptedBackend(['{"provider_id": "groq"}', '{"provider_id": "groq"}'])
    freellm.set_backend(backend)

    with pytest.raises(ExtractionFailedError):
        asyncio.run(extract_record(current=None, page_text="page text", task_name="test"))
    assert len(backend.calls) == 2


def test_should_raise_when_llm_response_is_not_json(all_llm_keys_present):
    backend = ScriptedBackend(["not json at all"])
    freellm.set_backend(backend)

    with pytest.raises(ExtractionFailedError):
        asyncio.run(extract_record(current=None, page_text="page text", task_name="test"))


def test_should_propagate_all_providers_exhausted(all_llm_keys_present, groq_record):
    backend = ScriptedBackend([AllProvidersExhaustedError(["groq/llama"])])
    freellm.set_backend(backend)

    with pytest.raises(AllProvidersExhaustedError):
        asyncio.run(
            extract_record(current=groq_record, page_text="page text", task_name="test")
        )


def test_should_include_current_record_in_prompt_when_refreshing(all_llm_keys_present, groq_record):
    backend = ScriptedBackend([extracted_json()])
    freellm.set_backend(backend)

    asyncio.run(extract_record(current=groq_record, page_text="page text", task_name="test"))

    user_message = backend.calls[0][1]["content"]
    assert groq_record.provider_id in user_message
    assert "page text" in user_message
