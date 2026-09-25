"""HTML → readable text, plus the content hash that gates LLM calls.

Pricing pages are static markup almost everywhere the refresh pipeline
looks; a plain tag-strip covers them. `content_hash` is the signal
`runner.py` compares to `repository.get_page_hash(url)` to decide
whether a page changed enough to spend an LLM call re-extracting it.
"""

from __future__ import annotations

import hashlib
import re

from selectolax.parser import HTMLParser

MAX_CHARS = 20_000

# Elements whose text is noise for a pricing extraction: scripts, styles,
# nav chrome, footers, and inline SVG icon markup.
_DROP_TAGS = ("script", "style", "nav", "footer", "svg", "noscript")
_WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Strip `html` down to the visible, readable text a human would scan.

    Drops script/style/nav/footer/svg, collapses runs of whitespace into
    single spaces, and caps the result at `MAX_CHARS` so a single page
    never blows the LLM's context budget.
    """
    tree = HTMLParser(html)
    for tag in _DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    text = tree.body.text(separator=" ", strip=True) if tree.body else tree.text()
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
    return text


def content_hash(text: str) -> str:
    """sha256 of the cleaned text — stable across whitespace-only re-fetches."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
