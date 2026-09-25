"""`GET /api/freellm/catalog` and `GET /api/freellm/plan` — shape parity with `backend/main.py`."""

from __future__ import annotations


def test_should_return_catalog_grouped_by_modality(client):
    response = client.get("/api/freellm/catalog")
    assert response.status_code == 200
    body = response.json()
    assert "modalities" in body
    assert "by_modality" in body
    assert body["total"] == sum(len(v) for v in body["by_modality"].values())


def test_should_return_plan_for_text_modality(client):
    response = client.get("/api/freellm/plan", params={"modality": "text"})
    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "text"
    assert "options" in body
    assert "chosen" in body


def test_should_422_on_unknown_modality(client):
    response = client.get("/api/freellm/plan", params={"modality": "not-a-modality"})
    assert response.status_code == 422
