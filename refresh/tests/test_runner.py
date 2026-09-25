from __future__ import annotations

import asyncio
import uuid

import httpx

import freellm
from domain.runs import Candidate, RefreshOptions, RunReport
from freellm import AllProvidersExhaustedError
from refresh.fetch import PoliteFetcher
from refresh.runner import create_runner
from refresh.text import content_hash, html_to_text
from refresh.tests.conftest import ScriptedBackend, extracted_json

PRICING_HTML = (
    "<html><body><p>Free tier: 100 requests/day, always free. "
    + ("Details about the plan and limits go here. " * 20)
    + "</p></body></html>"
)


def _report(options: RefreshOptions, *, trigger: str = "test") -> RunReport:
    return RunReport(run_id=str(uuid.uuid4()), trigger=trigger, options=options)  # type: ignore[arg-type]


def _fetcher_factory(handler):
    def factory(repository) -> PoliteFetcher:
        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        return PoliteFetcher(repository, min_interval_s=0, client=client)

    return factory


def _pricing_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(404)
    return httpx.Response(200, text=PRICING_HTML)


def _all_disallowed_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /")
    return httpx.Response(200, text=PRICING_HTML)


def _seed(repo, *records):
    for record in records:
        repo.save_provider(record, source="seed")


def test_should_skip_provider_when_robots_disallows(repo, groq_record):
    _seed(repo, groq_record)
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_all_disallowed_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.outcomes[0].status == "skipped"
    assert "robots" in finished.outcomes[0].message


def test_should_skip_llm_when_page_unchanged(repo, groq_record):
    _seed(repo, groq_record)
    for url in groq_record.source_urls:
        repo.set_page_hash(url, content_hash(html_to_text(PRICING_HTML)))

    freellm.set_backend(ScriptedBackend([]))  # queue empty -> would raise if called
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.outcomes[0].status == "unchanged"
    assert finished.llm_calls == 0


def test_should_update_provider_on_extract_happy_path(repo, groq_record, all_llm_keys_present):
    _seed(repo, groq_record)
    freellm.set_backend(
        ScriptedBackend([extracted_json(headline="A brand new headline for Groq")])
    )
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.outcomes[0].status == "updated"
    assert finished.llm_calls == 1
    updated = repo.get_provider("groq")
    assert updated.headline == "A brand new headline for Groq"


def test_should_retry_validation_then_fail_and_record_outcome(
    repo, groq_record, all_llm_keys_present
):
    _seed(repo, groq_record)
    freellm.set_backend(ScriptedBackend(['{"bad": true}', '{"bad": true}']))
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.outcomes[0].status == "failed"
    assert "extraction failed" in finished.outcomes[0].message


def test_should_never_wipe_services_via_merge_on_low_confidence_extraction(
    repo, groq_record, all_llm_keys_present
):
    _seed(repo, groq_record)
    freellm.set_backend(
        ScriptedBackend([extracted_json(services=[], parse_confidence="medium")])
    )
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    asyncio.run(runner.run(report))

    updated = repo.get_provider("groq")
    assert updated.services == groq_record.services


def test_should_queue_verify_when_confidence_low(repo, groq_record, all_llm_keys_present):
    _seed(repo, groq_record)
    freellm.set_backend(ScriptedBackend([extracted_json(parse_confidence="low")]))
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.outcomes[0].status == "queued-verify"
    assert len(repo.list_verify("pending")) == 1


def test_should_skip_remaining_providers_when_llm_budget_exhausted(
    repo, all_llm_keys_present, sample_records
):
    _seed(repo, *sample_records)
    freellm.set_backend(ScriptedBackend([extracted_json()]))
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    provider_ids = [r.provider_id for r in sample_records]
    report = _report(RefreshOptions(provider_ids=provider_ids, max_llm_calls=1))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    statuses = [o.status for o in finished.outcomes]
    assert statuses.count("skipped") >= 1
    assert any("budget exhausted" in o.message for o in finished.outcomes if o.status == "skipped")


def test_should_skip_remaining_providers_when_all_providers_exhausted(
    repo, all_llm_keys_present, sample_records
):
    _seed(repo, *sample_records)
    freellm.set_backend(ScriptedBackend([AllProvidersExhaustedError(["groq/llama"])]))
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    provider_ids = [r.provider_id for r in sample_records]
    report = _report(RefreshOptions(provider_ids=provider_ids, max_llm_calls=50))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    statuses = [o.status for o in finished.outcomes]
    assert statuses.count("skipped") == len(provider_ids)
    assert all("exhausted" in o.message for o in finished.outcomes)


def test_should_report_partial_status_when_some_providers_fail(repo, groq_record):
    _seed(repo, groq_record)
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_all_disallowed_handler))
    report = _report(RefreshOptions(provider_ids=["groq", "unknown-id"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.status == "partial"


def test_should_continue_other_providers_when_one_raises_unexpectedly(
    repo, groq_record, monkeypatch
):
    _seed(repo, groq_record)
    for url in groq_record.source_urls:
        repo.set_page_hash(url, content_hash(html_to_text(PRICING_HTML)))
    real_get = repo.get_provider

    def exploding_get(provider_id):
        if provider_id == "boom":
            raise RuntimeError("corrupt row")
        return real_get(provider_id)

    monkeypatch.setattr(repo, "get_provider", exploding_get)
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["boom", "groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    statuses = {o.provider_id: o.status for o in finished.outcomes}
    assert statuses == {"boom": "failed", "groq": "unchanged"}
    assert finished.status == "partial"


def test_should_report_failed_status_when_all_providers_fail(repo):
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["no-such-provider"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.status == "failed"


def test_should_report_succeeded_status_when_all_unchanged(repo, groq_record):
    _seed(repo, groq_record)
    for url in groq_record.source_urls:
        repo.set_page_hash(url, content_hash(html_to_text(PRICING_HTML)))

    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert finished.status == "succeeded"


def test_should_call_update_run_after_each_provider(repo, groq_record, monkeypatch, all_llm_keys_present):
    _seed(repo, groq_record)
    calls = {"n": 0}
    original_update_run = repo.update_run

    def counting_update_run(report):
        calls["n"] += 1
        original_update_run(report)

    monkeypatch.setattr(repo, "update_run", counting_update_run)
    freellm.set_backend(ScriptedBackend([extracted_json()]))
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=["groq"]))
    repo.create_run(report)

    asyncio.run(runner.run(report))

    # once after the provider, once for the final save
    assert calls["n"] >= 2


def test_should_import_approved_candidate_as_new_provider(repo, all_llm_keys_present):
    candidate = Candidate(
        candidate_id="abc123",
        url="https://new-free-thing.com/pricing",
        domain="new-free-thing.com",
        title="New Free Thing",
        status="approved",
    )
    repo.add_candidates([candidate])
    repo.set_candidate_status("abc123", "approved")

    freellm.set_backend(
        ScriptedBackend([extracted_json(provider_id="new-free-thing", name="New Free Thing")])
    )
    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_pricing_handler))
    report = _report(RefreshOptions(provider_ids=[]))
    repo.create_run(report)

    asyncio.run(runner.run(report))

    imported = repo.get_provider("new-free-thing-com")
    assert imported is not None
    assert imported.source_urls == ["https://new-free-thing.com/pricing"]
    assert len(repo.list_candidates("imported")) == 1


def test_should_leave_candidate_approved_when_import_fetch_fails(repo, all_llm_keys_present):
    candidate = Candidate(
        candidate_id="abc123",
        url="https://blocked-thing.com/pricing",
        domain="blocked-thing.com",
        title="Blocked Thing",
        status="approved",
    )
    repo.add_candidates([candidate])
    repo.set_candidate_status("abc123", "approved")

    runner = create_runner(repo, fetcher_factory=_fetcher_factory(_all_disallowed_handler))
    report = _report(RefreshOptions(provider_ids=[]))
    repo.create_run(report)

    finished = asyncio.run(runner.run(report))

    assert repo.get_provider("blocked-thing-com") is None
    assert len(repo.list_candidates("approved")) == 1
    assert finished.errors
