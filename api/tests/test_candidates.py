"""`GET /api/candidates` and admin approve/reject."""

from __future__ import annotations

from domain.runs import Candidate


def _candidate(candidate_id: str = "cand-1") -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        url="https://example.com/free-tier",
        domain="example.com",
        title="Example free tier",
    )


def test_should_list_pending_candidates(client, repository):
    repository.add_candidates([_candidate()])
    response = client.get("/api/candidates")
    assert response.status_code == 200
    assert [c["candidate_id"] for c in response.json()] == ["cand-1"]


def test_should_approve_candidate(client, repository):
    repository.add_candidates([_candidate()])
    response = client.post("/api/candidates/cand-1/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_should_reject_candidate(client, repository):
    repository.add_candidates([_candidate()])
    response = client.post("/api/candidates/cand-1/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_should_404_when_candidate_unknown(client):
    response = client.post("/api/candidates/missing/approve")
    assert response.status_code == 404


def test_should_401_when_key_wrong(client, repository):
    repository.add_candidates([_candidate()])
    response = client.post(
        "/api/candidates/cand-1/approve", headers={"X-ResourceOS-Key": "wrong"}
    )
    assert response.status_code == 401
