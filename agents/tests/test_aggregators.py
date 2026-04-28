"""Aggregator HTML link extraction."""

from __future__ import annotations

from agents.aggregators import (
    AGGREGATORS,
    AggregatorSource,
    extract_external_links,
    hosts_in_aggregator_links,
)


SAMPLE_HTML = """
<html><body>
  <nav><a href="/about">About</a></nav>
  <h1>Free credits for startups</h1>
  <ul>
    <li><a href="https://aws.amazon.com/activate">AWS Activate</a></li>
    <li><a href="https://gcp-startups.example.com/">GCP for Startups</a></li>
    <li><a href="https://twitter.com/some-handle">Twitter</a></li>
    <li><a href="mailto:hi@example.com">Email us</a></li>
    <li><a href="#section">Section anchor</a></li>
    <li><a href="https://aws.amazon.com/activate">AWS Activate (dup)</a></li>
    <li><a href="https://newprovider.io/free?ref=blog">New Provider</a></li>
  </ul>
</body></html>
"""


def test_extract_external_links_filters_correctly():
    links = extract_external_links(
        html=SAMPLE_HTML,
        base_url="https://grants.example.org/",
        skip_patterns=("twitter.com", "mailto:"),
    )
    # Same-host (none here) + skip patterns + fragments + dup all dropped.
    assert "https://aws.amazon.com/activate" in links
    assert "https://gcp-startups.example.com" in links or any(
        "gcp-startups" in u for u in links
    )
    assert all("twitter.com" not in u for u in links)
    assert all("mailto:" not in u for u in links)
    # Query string + trailing slash dedupe — newprovider must appear once.
    newprov = [u for u in links if "newprovider" in u]
    assert len(newprov) == 1


def test_extract_external_links_dedups_via_normalized_form():
    html = """
    <html><body>
      <a href="https://x.test/foo/">x1</a>
      <a href="https://x.test/foo">x2</a>
      <a href="https://x.test/foo?q=1">x3</a>
    </body></html>
    """
    links = extract_external_links(html=html, base_url="https://aggregator.test/")
    # All three normalize to the same form -> 1 link
    assert len([u for u in links if "x.test" in u]) == 1


def test_extract_external_links_skips_same_host():
    html = '<a href="https://aggregator.test/inner-page">inner</a><a href="https://other.test/">other</a>'
    links = extract_external_links(html=html, base_url="https://aggregator.test/")
    assert "https://aggregator.test/inner-page" not in links
    assert any("other.test" in u for u in links)


def test_aggregator_source_has_user_flagged_url():
    """grants.startupspeedrun.org must be in the curated AGGREGATORS list."""
    urls = [s.url for s in AGGREGATORS]
    assert any("startupspeedrun.org" in u for u in urls)


def test_hosts_in_aggregator_links_normalizes_case():
    hosts = hosts_in_aggregator_links(
        ["https://Example.COM/path", "https://other.test/"]
    )
    assert "example.com" in hosts
    assert "other.test" in hosts


def test_aggregator_source_skip_patterns_default_includes_socials():
    src = AggregatorSource(url="https://x.test/", category_hint="grant")
    assert "twitter.com" in src.skip_patterns
    assert "facebook.com" in src.skip_patterns
    assert "mailto:" in src.skip_patterns
