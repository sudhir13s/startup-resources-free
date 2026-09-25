"""`GET /api/changes` — since filter + limit."""

from __future__ import annotations

from datetime import date, timedelta


def test_should_return_new_change_for_each_seeded_provider(client):
    response = client.get("/api/changes")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["items"]) == 3
    assert all(item["severity"] == "new" for item in body["items"])


def test_should_filter_by_since_date(client):
    future = (date.today() + timedelta(days=1)).isoformat()
    response = client.get("/api/changes", params={"since": future})
    assert response.json()["total"] == 0


def test_should_respect_limit(client):
    response = client.get("/api/changes", params={"limit": 1})
    assert len(response.json()["items"]) == 1


def test_should_reject_limit_out_of_range(client):
    response = client.get("/api/changes", params={"limit": 0})
    assert response.status_code == 422
