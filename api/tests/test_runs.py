"""`GET /api/runs` and `GET /api/runs/{run_id}`."""

from __future__ import annotations

from domain.runs import RefreshOptions, RunReport


def test_should_return_empty_list_when_no_runs(client):
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_should_list_and_fetch_a_run(client, repository):
    report = RunReport(run_id="run-abc", trigger="test", options=RefreshOptions())
    repository.create_run(report)

    listed = client.get("/api/runs")
    assert listed.status_code == 200
    assert [r["run_id"] for r in listed.json()] == ["run-abc"]

    fetched = client.get("/api/runs/run-abc")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == "run-abc"


def test_should_404_when_run_unknown(client):
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404
    assert "detail" in response.json()
