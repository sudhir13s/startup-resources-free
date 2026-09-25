"""`GET /api/health` and lifespan seed import."""

from __future__ import annotations

from storage.sqlite_repository import SqliteRepository


def test_should_report_ok_status_and_service_name(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service_name"] == "ResourceOS API"
    assert "version" in body


def test_should_have_null_data_synced_at_when_no_sync_configured(client):
    body = client.get("/api/health").json()
    assert body["data_synced_at"] is None


def test_should_404_at_root_now_that_the_index_is_gone(client):
    # The API is fully private; the old `/` index just pointed at `/docs`,
    # which is disabled too. Nothing should be served at `/` anymore.
    response = client.get("/")
    assert response.status_code == 404


def test_should_import_seed_on_startup(client, repository: SqliteRepository):
    assert repository.get_provider("aws-free-tier") is not None
    assert repository.get_provider("groq") is not None
    assert repository.get_provider("startup-india-seed-fund") is not None
