"""Phase 10 extras: reporting a mistake, trends, bulk scans, API keys, and proxy-aware limits.
The sandbox and recon are fakes, and the database is the in-memory stand-in from conftest.py."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app import access, cache, extras, recon, sandbox_client
from app.config import Settings, get_settings
from app.main import app
from app.recon.models import Recon

VISIT = {
    "requested_url": "https://example.com/",
    "final_url": "https://example.com/",
    "hops": [{"url": "https://example.com/", "kind": "start", "status": 200}],
    "contacted_domains": ["example.com"],
    "blocked": [],
    "screenshot_jpeg_b64": None,
    "html": "<title>Example</title><p>Just a page.</p>",
    "stopped": None,
}


@pytest.fixture
def fakes(monkeypatch):
    order = []

    async def fake_visit(sandbox_url, url):
        order.append(url)
        return json.loads(json.dumps(VISIT)) | {"requested_url": url, "final_url": url}

    async def fake_recon(visit, url):
        return Recon(host="example.com", registered_domain="example.com")

    monkeypatch.setattr(sandbox_client, "visit", fake_visit)
    monkeypatch.setattr(recon, "run_recon", fake_recon)
    access.forget()
    return order


@pytest.fixture
def settings_override():
    def use(**changes):
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **changes)

    yield use
    app.dependency_overrides.clear()


def wait_for(client: TestClient, scan_id: str) -> dict:
    for _ in range(100):
        resp = client.get(f"/scans/{scan_id}")
        if resp.status_code == 200:
            return resp.json()
        time.sleep(0.05)
    raise AssertionError("the scan never finished")


# ---------- report a mistake ----------


def test_feedback_is_saved_with_the_verdict_and_without_email_addresses(fakes, monkeypatch):
    stored = []

    async def keep(database_url, scan_id, kind, note, analysis):
        stored.append((scan_id, kind, note, analysis["verdict"]))

    monkeypatch.setattr(extras, "save_feedback", keep)
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "example.com"}).json()
        body = {"kind": "false_alarm", "note": "This is my own shop, ask me at owner@example.org"}
        resp = client.post(f"/scans/{scan['id']}/feedback", json=body)
    assert resp.status_code == 201 and resp.json() == {"saved": True}
    assert stored == [(scan["id"], "false_alarm", "This is my own shop, ask me at REDACTED", "safe")]


def test_feedback_needs_a_real_scan_and_a_known_kind(fakes):
    with TestClient(app) as client:
        assert client.post("/scans/not-a-uuid/feedback", json={"kind": "other"}).status_code == 404
        missing = "00000000-0000-0000-0000-000000000000"
        assert client.post(f"/scans/{missing}/feedback", json={"kind": "other"}).status_code == 404
        scan = client.post("/scan", json={"url": "example.com"}).json()
        assert client.post(f"/scans/{scan['id']}/feedback", json={"kind": "rude"}).status_code == 422
        long_note = {"kind": "other", "note": "x" * 501}
        assert client.post(f"/scans/{scan['id']}/feedback", json=long_note).status_code == 422


def test_feedback_is_rate_limited(fakes, monkeypatch):
    async def keep(*args):
        pass

    monkeypatch.setattr(extras, "save_feedback", keep)
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "example.com"}).json()
        codes = [
            client.post(f"/scans/{scan['id']}/feedback", json={"kind": "other"}).status_code
            for _ in range(extras.FEEDBACK_PER_HOUR + 1)
        ]
    assert codes[:-1] == [201] * extras.FEEDBACK_PER_HOUR and codes[-1] == 429


# ---------- trends ----------


def test_trends_are_served_and_cached(monkeypatch):
    calls = []

    async def fake(database_url):
        calls.append(1)
        return {"days": [{"date": "2026-10-02", "safe": 3, "suspicious": 1, "dangerous": 2}], "brands": []}

    monkeypatch.setattr(extras, "read_trends", fake)
    with TestClient(app) as client:
        first = client.get("/trends").json()
        client.get("/trends")
    assert first["days"][0]["dangerous"] == 2
    assert len(calls) == 1  # the second call came from the cache


def test_trends_say_so_when_the_database_is_down(monkeypatch):
    async def broken(database_url):
        raise ConnectionError("down")

    cache.clear()
    monkeypatch.setattr(extras, "read_trends", broken)
    resp = TestClient(app).get("/trends")
    assert resp.status_code == 503 and "can't be read" in resp.json()["detail"]


# ---------- several links at once ----------


def test_bulk_scans_run_one_after_another_and_bad_links_are_refused(fakes):
    links = ["example.com/a", "javascript:alert(1)", "example.com/b"]
    with TestClient(app) as client:
        resp = client.post("/scans/bulk", json={"urls": links})
        assert resp.status_code == 202
        entries = resp.json()["scans"]
        assert [e["url"] for e in entries] == [
            "https://example.com/a",
            "javascript:alert(1)",
            "https://example.com/b",
        ]
        assert entries[1]["id"] is None and "Only http and https" in entries[1]["error"]
        results = [wait_for(client, e["id"]) for e in entries if e["id"]]
    assert [r["url"] for r in results] == ["https://example.com/a", "https://example.com/b"]
    assert fakes == ["https://example.com/a", "https://example.com/b"]  # in order, never in parallel


def test_bulk_takes_at_most_ten_links_and_respects_the_hourly_limit(fakes, settings_override):
    with TestClient(app) as client:
        too_many = client.post("/scans/bulk", json={"urls": ["example.com"] * 11})
        assert too_many.status_code == 422
        assert client.post("/scans/bulk", json={"urls": []}).status_code == 422
    settings_override(scan_rate_limit_per_hour=2)
    with TestClient(app) as client:
        entries = client.post(
            "/scans/bulk", json={"urls": ["example.com/1", "example.com/2", "example.com/3"]}
        ).json()["scans"]
        assert [bool(e["id"]) for e in entries] == [True, True, False]
        assert entries[2]["error"] == "Your hourly scan limit is used up."
        again = client.post("/scans/bulk", json={"urls": ["example.com/4"]})
    assert again.status_code == 429


# ---------- API keys and limits ----------


def test_keys_are_random_and_only_their_hash_is_kept():
    key = access.new_key()
    assert key.startswith("ll_") and len(key) > 40
    assert access.new_key() != key
    assert len(access.key_hash(key)) == 32 and access.key_hash(key) == access.key_hash(key)
    assert key.encode() not in access.key_hash(key)


def test_a_valid_key_gets_its_own_higher_limit(fakes, settings_override, monkeypatch):
    async def lookup(database_url, key):
        return (7, 5) if key == "ll_good" else None

    monkeypatch.setattr(access, "_lookup", lookup)
    settings_override(scan_rate_limit_per_hour=1)
    with TestClient(app) as client:
        anonymous = [client.post("/scan", json={"url": "example.com"}).status_code for _ in range(2)]
        with_key = [
            client.post("/scan", json={"url": "example.com"}, headers={"X-API-Key": "ll_good"}).status_code
            for _ in range(6)
        ]
        bad = client.post("/scan", json={"url": "example.com"}, headers={"X-API-Key": "ll_wrong"})
        not_ours = client.post("/scan", json={"url": "example.com"}, headers={"X-API-Key": "something"})
    assert anonymous == [200, 429]
    assert with_key == [200] * 5 + [429]
    assert bad.status_code == 401 and not_ours.status_code == 401
    assert "isn't valid" in bad.json()["detail"]


def test_the_scanner_can_be_closed_to_callers_without_a_key(fakes, settings_override):
    settings_override(require_api_key=True)
    with TestClient(app) as client:
        resp = client.post("/scans", json={"url": "example.com"})
    assert resp.status_code == 401 and "needs an API key" in resp.json()["detail"]


def test_forwarded_addresses_count_only_behind_a_trusted_proxy(fakes, settings_override):
    def scan(client, address):
        headers = {"X-Forwarded-For": f"203.0.113.9, {address}"}
        return client.post("/scan", json={"url": "example.com"}, headers=headers).status_code

    settings_override(scan_rate_limit_per_hour=1)
    with TestClient(app) as client:
        # Not behind a proxy: the header is ignored, so both calls count as the same caller.
        assert [scan(client, "198.51.100.1"), scan(client, "198.51.100.2")] == [200, 429]
    settings_override(scan_rate_limit_per_hour=1, trust_forwarded_for=True)
    with TestClient(app) as client:
        # Behind a trusted proxy: the address the proxy added (the last one) is the caller.
        assert [scan(client, "198.51.100.3"), scan(client, "198.51.100.4"), scan(client, "198.51.100.3")] == [
            200,
            200,
            429,
        ]


def test_status_never_says_404_for_a_running_scan(fakes):
    with TestClient(app) as client:
        assert client.get("/scans/not-a-uuid/status").json() == {"state": "unknown"}
        missing = "00000000-0000-0000-0000-000000000000"
        assert client.get(f"/scans/{missing}/status").json() == {"state": "unknown"}
        scan_id = client.post("/scans/bulk", json={"urls": ["example.com"]}).json()["scans"][0]["id"]
        wait_for(client, scan_id)
        assert client.get(f"/scans/{scan_id}/status").json() == {
            "state": "done",
            "verdict": "safe",
            "score": 0,
        }
