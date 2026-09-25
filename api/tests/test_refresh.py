"""`POST /api/refresh` and `GET /api/refresh/status` — the background-task path."""

from __future__ import annotations

import time

from api.tests.conftest import ADMIN_TOKEN, FakeRunner, FakeSync, make_client
from domain.runs import RefreshOptions, RunReport


def _wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_should_202_and_run_in_background_then_push(repository, seed_file):
    runner = FakeRunner(outcome="succeeded")
    sync = FakeSync()
    client_gen = make_client(
        repository, seed_file, sync=sync, runner_factory=lambda repo: runner
    )
    client = next(client_gen)
    try:
        response = client.post("/api/refresh", json={}, headers={"X-Admin-Token": ADMIN_TOKEN})
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        assert _wait_until(lambda: repository.get_run(run_id).status == "succeeded")
        assert len(sync.pushed) == 1
        assert repository.get_run(run_id).data_pushed is True

        status = client.get("/api/refresh/status").json()
        assert status["last"]["run_id"] == run_id
        assert status["data_synced_at"] is not None
    finally:
        client_gen.close()


def test_should_409_when_run_already_active(repository, seed_file):
    active = RunReport(run_id="already-running", trigger="test", options=RefreshOptions())
    repository.create_run(active)
    client_gen = make_client(repository, seed_file)
    client = next(client_gen)
    try:
        response = client.post("/api/refresh", json={}, headers={"X-Admin-Token": ADMIN_TOKEN})
        assert response.status_code == 409
        assert response.json()["detail"] == "A refresh is already running"
    finally:
        client_gen.close()


def test_should_401_when_admin_token_missing(client):
    response = client.post("/api/refresh", json={})
    assert response.status_code == 401


def test_should_503_when_admin_token_not_configured(repository, seed_file):
    client_gen = make_client(repository, seed_file, admin_token=None)
    client = next(client_gen)
    try:
        response = client.post("/api/refresh", json={}, headers={"X-Admin-Token": "anything"})
        assert response.status_code == 503
    finally:
        client_gen.close()


def test_should_mark_run_failed_when_runner_raises(repository, seed_file):
    runner = FakeRunner(outcome="raise")
    client_gen = make_client(repository, seed_file, runner_factory=lambda repo: runner)
    client = next(client_gen)
    try:
        response = client.post("/api/refresh", json={}, headers={"X-Admin-Token": ADMIN_TOKEN})
        run_id = response.json()["run_id"]
        assert _wait_until(lambda: repository.get_run(run_id).status == "failed")
        report = repository.get_run(run_id)
        assert report.errors and "boom" in report.errors[0]
    finally:
        client_gen.close()


def test_should_return_empty_status_when_no_runs_yet(client):
    response = client.get("/api/refresh/status")
    assert response.status_code == 200
    body = response.json()
    assert body["active"] is None
    assert body["last"] is None


def test_should_finish_run_when_push_raises_unexpected_error(repository, seed_file):
    sync = FakeSync(push_error=OSError("disk full"))
    client_gen = make_client(
        repository, seed_file, sync=sync, runner_factory=lambda repo: FakeRunner()
    )
    client = next(client_gen)
    try:
        response = client.post("/api/refresh", json={}, headers={"X-Admin-Token": ADMIN_TOKEN})
        run_id = response.json()["run_id"]

        assert _wait_until(lambda: repository.get_run(run_id).status != "running")
        run = repository.get_run(run_id)
        assert run.data_pushed is False
        assert any("disk full" in error for error in run.errors)
        assert repository.active_run() is None
    finally:
        client_gen.close()
