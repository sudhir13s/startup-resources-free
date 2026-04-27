"""Agents — LLM-driven processing of scraped provider data.

Pipeline order:

    research.find_candidates(query)
        -> list[CandidateURL]
    extractor.extract_record(html, url)
        -> ProviderRecord (parse_confidence: high|medium|low)
    tier_classifier.assign_tiers(record)
        -> ProviderRecord with use_case_tiers + tier_fit_rationale set
    change_detector.diff_against_last(today, yesterday)   # pure code, no LLM
        -> ChangeReport
    verifier.queue_low_confidence(record)
        -> filesystem / DB write of low-confidence rows for human review

Every agent that calls an LLM goes through `agents.llm.call_structured`,
which wraps `freellm.call_text` with Pydantic response_model enforcement.
That wrapper is the only place this module imports `freellm`.

Vendor-neutrality: per `agentic-pipeline.md`, no LangGraph / CrewAI /
OpenAI Agents SDK / Anthropic Agent SDK as default. Direct functions
+ a minimal in-repo orchestrator only.
"""

from __future__ import annotations

from agents.change_detector import ChangeReport, diff_against_last
from agents.extractor import extract_record
from agents.research import CandidateURL, find_candidates
from agents.tier_classifier import assign_tiers
from agents.verifier import queue_low_confidence

__all__ = [
    "CandidateURL",
    "ChangeReport",
    "assign_tiers",
    "diff_against_last",
    "extract_record",
    "find_candidates",
    "queue_low_confidence",
]
