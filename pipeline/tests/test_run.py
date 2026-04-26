from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from pipeline.run import main


def test_pipeline_dry_run_lists_collectors():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--dry-run"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["dry_run"] is True
    ids = [w["provider_id"] for w in payload["would_fetch"]]
    assert "vercel" in ids
    assert "render" in ids
    assert "groq" in ids


def test_pipeline_dry_run_with_filter():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--dry-run", "--providers", "groq"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    ids = [w["provider_id"] for w in payload["would_fetch"]]
    assert ids == ["groq"]


def test_pipeline_dry_run_unknown_provider():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--dry-run", "--providers", "nope-not-real"])
    assert rc == 2
    payload = json.loads(buf.getvalue())
    assert "error" in payload
