"""/api/verify-queue endpoints — drives the dashboard Verify tab."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = BACKEND_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.verifier import VerifyItem  # noqa: E402

import db as db_module  # type: ignore[import-untyped]  # noqa: E402
from main import app  # noqa: E402


client = TestClient(app)


@pytest.fixture
def empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point RESOURCEOS_DB_PATH at a fresh tmp file. Migrations applied."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(db_path))
    with db_module.db_session() as conn:
        db_module.apply_migrations(conn)
    return db_path


@pytest.fixture
def queued_db(empty_db: Path):
    """Two pending entries + one resolved."""
    items = [
        VerifyItem(
            record_id=f"rec-{i}",
            provider_id=f"prov-{i}",
            provider_name=f"Provider {i}",
            source_url=f"https://example{i}.test/",
            parse_confidence="low",
            reason=f"missing-{i}",
            queued_at=datetime.now(tz=timezone.utc).isoformat(),
            record_payload={"id": f"rec-{i}"},
        )
        for i in range(3)
    ]
    with db_module.db_session() as conn:
        for item in items:
            db_module.enqueue_verify(conn, item)
        # Pre-resolve the third one.
        db_module.resolve_verify(
            conn, "rec-2", status="confirmed", resolved_by="seeded"
        )
    return empty_db


# ---------- list ----------


def test_verify_queue_empty_when_db_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(tmp_path / "missing.db"))
    r = client.get("/api/verify-queue")
    assert r.status_code == 200
    body = r.json()
    assert body == {"total": 0, "items": []}


def test_verify_queue_lists_pending(queued_db: Path):
    r = client.get("/api/verify-queue")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2  # rec-2 was resolved
    record_ids = {i["record_id"] for i in body["items"]}
    assert record_ids == {"rec-0", "rec-1"}


# ---------- confirm ----------


def test_confirm_pending_record(queued_db: Path):
    r = client.post(
        "/api/verify-queue/rec-0/confirm",
        params={"resolved_by": "tester"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "record_id": "rec-0",
        "status": "confirmed",
        "resolved_by": "tester",
    }
    # Re-list — only rec-1 still pending.
    r2 = client.get("/api/verify-queue")
    assert r2.json()["total"] == 1


def test_confirm_unknown_record_404(queued_db: Path):
    r = client.post("/api/verify-queue/does-not-exist/confirm")
    assert r.status_code == 404


def test_confirm_already_resolved_404(queued_db: Path):
    """rec-2 was pre-resolved -> confirming again must 404."""
    r = client.post("/api/verify-queue/rec-2/confirm")
    assert r.status_code == 404


def test_confirm_db_absent_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(tmp_path / "no-db.db"))
    r = client.post("/api/verify-queue/anything/confirm")
    assert r.status_code == 404


# ---------- reject ----------


def test_reject_pending_record(queued_db: Path):
    r = client.post("/api/verify-queue/rec-1/reject")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    # Pending count drops by 1.
    r2 = client.get("/api/verify-queue")
    assert r2.json()["total"] == 1


def test_reject_unknown_record_404(queued_db: Path):
    r = client.post("/api/verify-queue/does-not-exist/reject")
    assert r.status_code == 404
