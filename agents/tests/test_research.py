"""research agent — proposes candidate URLs."""

from __future__ import annotations

import asyncio
import json

from agents.research import find_candidates


def test_find_candidates_happy_path(scripted_backend):
    scripted_backend.script(
        "research",
        json.dumps(
            {
                "candidates": [
                    {
                        "url": "https://render.com/pricing",
                        "title": "Render Pricing",
                        "rationale": "official pricing page",
                        "is_official": True,
                    },
                    {
                        "url": "https://docs.render.com/free-tier",
                        "title": "Free Tier docs",
                        "rationale": "official free-tier docs",
                        "is_official": True,
                    },
                ]
            }
        ),
    )
    out = asyncio.run(find_candidates(query="Render hosting", backend=scripted_backend))
    assert len(out) == 2
    assert out[0].url == "https://render.com/pricing"
    assert all(c.is_official for c in out)


def test_find_candidates_caps_at_max_results(scripted_backend):
    scripted_backend.script(
        "research",
        json.dumps(
            {
                "candidates": [
                    {
                        "url": f"https://example.com/{i}",
                        "title": f"page {i}",
                        "rationale": "",
                        "is_official": False,
                    }
                    for i in range(8)
                ]
            }
        ),
    )
    out = asyncio.run(
        find_candidates(query="x", backend=scripted_backend, max_results=3)
    )
    assert len(out) == 3


def test_find_candidates_returns_empty_on_garbage(scripted_backend):
    scripted_backend.script("research", "not json at all")
    out = asyncio.run(find_candidates(query="x", backend=scripted_backend))
    assert out == []
