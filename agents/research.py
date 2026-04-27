"""Research agent — given a short query, propose candidate URLs.

Lightweight LLM call for now (the model uses its own knowledge to suggest
URLs). A follow-up batch can wire web search MCP / SerpAPI for live
discovery. For B2 we intentionally keep this LLM-only — the curator
runs it as a discovery aid, then a human (or `collectors/`) verifies the
URLs are real before committing them.

Returns `list[CandidateURL]`. Empty list on parse failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from agents.llm import call_structured


@dataclass
class CandidateURL:
    url: str
    title: str
    rationale: str
    is_official: bool


class _ResearchResponse(BaseModel):
    class _Item(BaseModel):
        url: HttpUrl
        title: str
        rationale: str = ""
        is_official: bool = False

    candidates: list[_Item] = Field(default_factory=list)


async def find_candidates(
    *,
    query: str,
    task_name: str = "research",
    backend: Any = None,
    max_results: int = 5,
) -> list[CandidateURL]:
    """Return up to `max_results` plausible URLs for the query.

    Empty list on LLM failure or empty response — the pipeline can fall
    back to manually curated URLs in that case.
    """
    sr = await call_structured(
        prompt_name="research",
        user_input=f"QUERY: {query}",
        response_model=_ResearchResponse,
        task_name=task_name,
        backend=backend,
        max_tokens=600,
        temperature=0.0,
    )
    if sr.parsed is None:
        return []
    parsed = sr.parsed
    assert isinstance(parsed, _ResearchResponse)
    return [
        CandidateURL(
            url=str(item.url),
            title=item.title,
            rationale=item.rationale,
            is_official=item.is_official,
        )
        for item in parsed.candidates[:max_results]
    ]
