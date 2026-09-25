"""The refresh pipeline: fetch -> extract -> merge -> persist -> discover.

`create_runner(repository)` is the only public entry the API imports (per
`refresh/contracts.py`). Each provider is processed independently so one
failure never aborts the run; `repository.update_run(report)` is called
after every provider so a restart loses at most one provider's work.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Callable

from domain.records import ProviderRecord
from domain.runs import ProviderOutcome, RunReport, VerifyItem
from domain.taxonomy import CATEGORIES
from freellm import AllProvidersExhaustedError
from refresh.discover import discover, known_domains
from refresh.extract import ExtractionFailedError, extract_record
from refresh.fetch import PoliteFetcher
from refresh.merge import merge
from refresh.search import get_chain
from refresh.text import content_hash
from storage.repository import Repository

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PROVIDERS = 5

FetcherFactory = Callable[[Repository], PoliteFetcher]


class Runner:
    """Implements the `RefreshRunner` protocol from `refresh/contracts.py`."""

    def __init__(
        self, repository: Repository, *, fetcher_factory: FetcherFactory | None = None
    ) -> None:
        self._repo = repository
        self._fetcher_factory: FetcherFactory = fetcher_factory or PoliteFetcher

    async def run(self, report: RunReport) -> RunReport:
        """Process every provider in `report.options`, then discovery and
        candidate import, and return the finished report. Never raises —
        every failure is recorded as an outcome or an entry in `errors`.
        """
        fetcher = self._fetcher_factory(self._repo)
        llm_budget = _Budget(report.options.max_llm_calls)
        try:
            provider_ids = self._target_provider_ids(report)
            await self._process_providers(report, provider_ids, fetcher, llm_budget)
            await self._import_approved_candidates(report, fetcher, llm_budget)
            if report.options.discover:
                await self._run_discovery(report, fetcher)
        except Exception as exc:  # noqa: BLE001 — the run must always finish and be saved
            report.errors.append(f"run crashed: {exc}")
            logger.exception("refresh_run_crashed", extra={"run_id": report.run_id})
        finally:
            await fetcher.aclose()

        report.status = _final_status(report)
        report.finished_at = datetime.now(tz=timezone.utc)
        self._repo.update_run(report)
        return report

    def _target_provider_ids(self, report: RunReport) -> list[str]:
        if report.options.provider_ids is not None:
            return list(report.options.provider_ids)
        return [p.provider_id for p in self._repo.list_providers()]

    async def _process_providers(
        self,
        report: RunReport,
        provider_ids: list[str],
        fetcher: PoliteFetcher,
        llm_budget: "_Budget",
    ) -> None:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROVIDERS)

        async def _bounded(provider_id: str) -> None:
            async with semaphore:
                try:
                    await self._process_one(report, provider_id, fetcher, llm_budget)
                except Exception as exc:  # noqa: BLE001 - one provider must never abort the run
                    report.outcomes.append(
                        ProviderOutcome(
                            provider_id=provider_id,
                            status="failed",
                            message=f"unexpected error: {type(exc).__name__}: {exc}",
                        )
                    )
            self._repo.update_run(report)

        # gather (not a sequential loop) so the semaphore actually allows
        # MAX_CONCURRENT_PROVIDERS providers in flight; per-host politeness
        # is still enforced inside PoliteFetcher.
        await asyncio.gather(*(_bounded(provider_id) for provider_id in provider_ids))

    async def _process_one(
        self,
        report: RunReport,
        provider_id: str,
        fetcher: PoliteFetcher,
        llm_budget: "_Budget",
    ) -> None:
        started = time.monotonic()
        current = self._repo.get_provider(provider_id)
        if current is None:
            report.outcomes.append(
                ProviderOutcome(
                    provider_id=provider_id, status="failed", message="unknown provider_id"
                )
            )
            return

        fetched = await self._fetch_all(current.source_urls, fetcher)
        if fetched is None:
            report.outcomes.append(
                _outcome(provider_id, started, status="skipped", message="robots.txt disallows fetch")
            )
            return
        if isinstance(fetched, str):
            report.outcomes.append(
                _outcome(provider_id, started, status="failed", message=fetched)
            )
            return

        texts_by_url, unchanged = fetched
        if unchanged and not report.options.force:
            self._repo.save_provider(current, source="refresh", run_id=report.run_id)
            report.outcomes.append(
                _outcome(provider_id, started, status="unchanged", message="page unchanged")
            )
            return

        if not llm_budget.has_room():
            report.outcomes.append(
                _outcome(
                    provider_id, started, status="skipped",
                    message="LLM call budget exhausted for this run",
                )
            )
            return

        await self._extract_merge_save(report, provider_id, current, texts_by_url, llm_budget, started)

    async def _fetch_all(
        self, source_urls: list[str], fetcher: PoliteFetcher
    ) -> tuple[dict[str, str], bool] | str | None:
        """Returns `(texts_by_url, all_unchanged)`, a failure message (str),
        or `None` when robots.txt blocked every source URL."""
        texts_by_url: dict[str, str] = {}
        all_unchanged = True
        any_ok = False
        for url in source_urls:
            outcome = await fetcher.fetch_with_follow(url)
            if outcome.robots_blocked:
                continue
            if not outcome.ok:
                return f"fetch failed for {url}: {outcome.error or outcome.status_code}"
            any_ok = True
            page_hash = content_hash(outcome.text) if outcome.text else None
            previous_hash = self._repo.get_page_hash(url)
            if page_hash != previous_hash:
                all_unchanged = False
            if outcome.text:
                texts_by_url[url] = outcome.text
        if not any_ok:
            return None
        return texts_by_url, all_unchanged

    async def _extract_merge_save(
        self,
        report: RunReport,
        provider_id: str,
        current: ProviderRecord | None,
        texts_by_url: dict[str, str],
        llm_budget: "_Budget",
        started: float,
    ) -> None:
        llm_budget.spend()
        report.llm_calls += 1
        page_text = "\n\n---PAGE BREAK---\n\n".join(texts_by_url.values())
        try:
            extraction = await extract_record(
                current=current, page_text=page_text, task_name=f"refresh:{provider_id}"
            )
        except AllProvidersExhaustedError:
            llm_budget.exhaust()
            report.outcomes.append(
                _outcome(
                    provider_id, started, status="skipped",
                    message="free LLM providers exhausted for this run",
                )
            )
            return
        except ExtractionFailedError as exc:
            report.outcomes.append(
                _outcome(provider_id, started, status="failed", message=f"extraction failed: {exc}")
            )
            return

        merged = merge(current, extraction.record)
        # Page hashes are set only after a successful extract, per URL.
        for url, text in texts_by_url.items():
            self._repo.set_page_hash(url, content_hash(text))

        if merged.parse_confidence == "low":
            self._enqueue_verify(report, provider_id, merged)
            report.outcomes.append(
                _outcome(
                    provider_id, started, status="queued-verify",
                    message="low confidence extraction sent to verify queue",
                    llm_provider=f"{extraction.provider_used}/{extraction.model_used}",
                )
            )
            return

        result = self._repo.save_provider(merged, source="refresh", run_id=report.run_id)
        status = "updated" if result.stored else "unchanged"
        report.outcomes.append(
            _outcome(
                provider_id, started, status=status,
                message=f"{len(result.changes)} field(s) changed" if result.stored else "no content change",
                llm_provider=f"{extraction.provider_used}/{extraction.model_used}",
                changes=len(result.changes),
            )
        )

    def _enqueue_verify(self, report: RunReport, provider_id: str, proposed: ProviderRecord) -> None:
        item_id = hashlib.sha1(f"{provider_id}:{report.run_id}".encode()).hexdigest()
        self._repo.enqueue_verify(
            VerifyItem(
                item_id=item_id, provider_id=provider_id, proposed=proposed,
                reason="low parse_confidence", run_id=report.run_id,
            )
        )

    async def _import_approved_candidates(
        self, report: RunReport, fetcher: PoliteFetcher, llm_budget: "_Budget"
    ) -> None:
        """Approved discovery candidates become new providers this run."""
        for candidate in self._repo.list_candidates("approved"):
            provider_id = _slug(candidate.domain or candidate.title)
            outcome = await fetcher.fetch_with_follow(candidate.url)
            if not outcome.ok:
                report.errors.append(f"candidate import failed for {candidate.url}: {outcome.error}")
                continue
            if not llm_budget.has_room():
                report.errors.append(f"candidate import skipped (LLM budget spent): {candidate.url}")
                continue
            llm_budget.spend()
            report.llm_calls += 1
            try:
                extraction = await extract_record(
                    current=None, page_text=outcome.text, task_name=f"candidate:{provider_id}"
                )
            except (AllProvidersExhaustedError, ExtractionFailedError) as exc:
                report.errors.append(f"candidate extraction failed for {candidate.url}: {exc}")
                continue
            record = extraction.record.model_copy(
                update={"provider_id": provider_id, "source_urls": [candidate.url]}
            )
            self._repo.save_provider(record, source="candidate", run_id=report.run_id)
            self._repo.set_candidate_status(candidate.candidate_id, "imported")

    async def _run_discovery(self, report: RunReport, fetcher: PoliteFetcher) -> None:
        try:
            chain = get_chain(self._repo)
            known = known_domains(self._repo.list_providers())
            outcome = await discover(
                chain=chain, fetcher=fetcher, known=known, categories=tuple(CATEGORIES)
            )
        except Exception as exc:  # noqa: BLE001 — discovery must not fail the run
            report.errors.append(f"discovery failed: {exc}")
            return
        report.search_calls += outcome.queries_run
        report.errors.extend(outcome.errors)
        report.candidates_found += self._repo.add_candidates(outcome.candidates)


class _Budget:
    """Tracks the run's LLM call budget and whether the chain is exhausted."""

    def __init__(self, max_calls: int) -> None:
        self._max_calls = max_calls
        self._used = 0
        self._exhausted = False

    def has_room(self) -> bool:
        return not self._exhausted and self._used < self._max_calls

    def spend(self) -> None:
        self._used += 1

    def exhaust(self) -> None:
        self._exhausted = True


def _outcome(
    provider_id: str,
    started: float,
    *,
    status: str,
    message: str,
    llm_provider: str | None = None,
    changes: int = 0,
) -> ProviderOutcome:
    return ProviderOutcome(
        provider_id=provider_id,
        status=status,  # type: ignore[arg-type]
        message=message,
        llm_provider=llm_provider,
        changes=changes,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def _final_status(report: RunReport) -> str:
    if not report.outcomes:
        return "failed" if report.errors else "succeeded"
    statuses = {o.status for o in report.outcomes}
    if statuses == {"failed"}:
        return "failed"
    if "failed" in statuses:
        return "partial"
    return "succeeded"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "candidate"


def create_runner(repository: Repository, *, fetcher_factory: FetcherFactory | None = None) -> Runner:
    """Build the `RefreshRunner` the API drives (`refresh/contracts.py`).

    `fetcher_factory` is test-only — production callers always get the
    default `PoliteFetcher`.
    """
    return Runner(repository, fetcher_factory=fetcher_factory)
