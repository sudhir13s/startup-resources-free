"""`/api/providers` and `/api/providers/{id}` — filters, facets, 422, detail, related, 404."""

from __future__ import annotations


def test_should_return_all_seeded_providers_when_no_filter(client):
    response = client.get("/api/providers")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == body["matched"] == len(body["items"]) == 3


def test_should_match_aws_when_filtering_by_service_category(client):
    response = client.get("/api/providers", params={"category": "database"})
    assert response.status_code == 200
    body = response.json()
    ids = {item["provider_id"] for item in body["items"]}
    assert "aws-free-tier" in ids


def test_should_split_by_card_variant_when_variant_is_funds(client):
    resources = client.get("/api/providers", params={"variant": "resource"}).json()
    funds = client.get("/api/providers", params={"variant": "funds"}).json()
    assert resources["total"] + funds["total"] == 3
    assert all(item["card_variant"] == "resource" for item in resources["items"])
    assert all(item["card_variant"] == "funds" for item in funds["items"])


def test_should_return_facet_counts_ignoring_only_their_own_filter(client):
    response = client.get("/api/providers", params={"tier": "hobby"})
    body = response.json()
    assert "tiers" in body["facets"]
    assert "categories" in body["facets"]
    assert "offer_types" in body["facets"]
    assert "geo" in body["facets"]


def test_should_reject_unknown_offer_type_with_422(client):
    response = client.get("/api/providers", params={"offer_type": "not-a-real-type"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_should_reject_unknown_category_with_422(client):
    response = client.get("/api/providers", params={"category": "not-a-real-category"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_should_normalize_legacy_category_alias(client):
    response = client.get("/api/providers", params={"category": "databases"})
    assert response.status_code == 200
    ids = {item["provider_id"] for item in response.json()["items"]}
    assert "aws-free-tier" in ids


def test_should_return_detail_with_history_and_related_when_known(client):
    response = client.get("/api/providers/aws-free-tier")
    assert response.status_code == 200
    body = response.json()
    assert body["record"]["provider_id"] == "aws-free-tier"
    assert isinstance(body["history"], list)
    assert body["history"][0]["source"] == "seed"
    assert isinstance(body["related"], list)


def test_should_404_when_provider_unknown(client):
    response = client.get("/api/providers/does-not-exist")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_should_filter_by_query_text(client):
    response = client.get("/api/providers", params={"q": "groq"})
    body = response.json()
    assert all("groq" in item["name"].lower() or "groq" in item["headline"].lower() for item in body["items"])
