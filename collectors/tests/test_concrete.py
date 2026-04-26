from __future__ import annotations

from collectors.ai_apis.groq import GroqCollector
from collectors.cloud.render import RenderCollector
from collectors.cloud.vercel import VercelCollector


VERCEL_HTML = """
<html><body>
  <h1>Hobby</h1>
  <p>Includes 100 GB bandwidth per month and free SSL.</p>
</body></html>
"""

VERCEL_HTML_BROKEN = """
<html><body>
  <h1>Pricing</h1>
  <p>Buy our pro plan for $20/month.</p>
</body></html>
"""

RENDER_HTML = """
<html><body>
  <h2>Free</h2>
  <p>750 hours / mo of free Web Service compute.</p>
</body></html>
"""

GROQ_HTML = """
<html><body>
  <pre>
  Free tier: 14,400 requests per day on Llama-3.3-70B-versatile.
  </pre>
</body></html>
"""


def test_vercel_extracts_bandwidth_quota():
    rec = VercelCollector().extract_fields(VERCEL_HTML)
    assert rec["id"] == "vercel"
    assert rec["quota_summary"] == "100 GB / mo"
    assert rec["parse_confidence"] == "medium"
    assert rec["india_accessible"] is True


def test_vercel_falls_back_to_low_confidence_on_broken_markup():
    rec = VercelCollector().extract_fields(VERCEL_HTML_BROKEN)
    assert rec["parse_confidence"] == "low"
    assert rec["quota_summary"] == ""


def test_render_extracts_hours_quota():
    rec = RenderCollector().extract_fields(RENDER_HTML)
    assert rec["id"] == "render"
    assert rec["quota_summary"] == "750 hrs / mo"
    assert rec["parse_confidence"] == "medium"


def test_groq_extracts_rpd():
    rec = GroqCollector().extract_fields(GROQ_HTML)
    assert rec["id"] == "groq"
    assert "14,400" in rec["quota_summary"]
    assert rec["parse_confidence"] == "medium"


def test_all_concrete_collectors_set_required_fields():
    for collector_cls in (VercelCollector, RenderCollector, GroqCollector):
        c = collector_cls()
        assert c.provider_id
        assert c.provider_name
        assert c.category
        assert c.source_url.startswith("https://")
        # extract_fields with empty body should still emit a low-confidence stub
        rec = c.extract_fields("")
        assert rec["id"] == c.provider_id
        assert rec["parse_confidence"] in {"low", "medium"}
