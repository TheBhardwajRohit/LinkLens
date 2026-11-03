"""Comparing a scan with VirusTotal and PhishTank. Both services are fakes; nothing here touches the
network, and the sandbox and recon are fakes too."""

import json
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app import access, compare, recon, sandbox_client
from app.blacklists import http, virustotal
from app.config import Settings, get_settings
from app.main import app
from app.recon.models import Recon

VISIT = {
    "hops": [],
    "contacted_domains": [],
    "blocked": [],
    "screenshot_jpeg_b64": None,
    "html": "<title>Example</title><p>Just a page.</p>",
    "stopped": None,
}
VT_REPORT = {
    "data": {
        "attributes": {
            "last_analysis_results": {
                "Alpha": {"category": "malicious", "result": "phishing"},
                "Beta": {"category": "harmless", "result": "clean"},
            },
            "last_analysis_stats": {"malicious": 1, "harmless": 1},
            "reputation": -5,
            "total_votes": {"malicious": 2, "harmless": 0},
            "first_submission_date": 1700000000,
        }
    }
}


@pytest.fixture
def scanner(monkeypatch):
    async def fake_visit(sandbox_url, url):
        return json.loads(json.dumps(VISIT)) | {"requested_url": url, "final_url": url}

    async def fake_recon(visit, url):
        return Recon(host="example.com", registered_domain="example.com")

    saved = []

    async def keep(database_url, scan_id, comparison):
        saved.append((scan_id, comparison))

    monkeypatch.setattr(sandbox_client, "visit", fake_visit)
    monkeypatch.setattr(recon, "run_recon", fake_recon)
    monkeypatch.setattr(compare, "save", keep)
    monkeypatch.setattr(compare, "FRESH_WAIT_S", 0)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, virustotal_api_key="test-key")
    access.forget()
    virustotal.reset()
    yield saved
    app.dependency_overrides.clear()


def services(monkeypatch, vt=None, phishtank=None) -> list[httpx.Request]:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "checkurl.phishtank.com":
            return (
                phishtank(request)
                if phishtank
                else httpx.Response(200, json={"results": {"in_database": False}})
            )
        return vt(request) if vt else httpx.Response(200, json=VT_REPORT)

    monkeypatch.setattr(http, "transport", httpx.MockTransport(handle))
    return calls


def test_compare_asks_both_services_about_the_cleaned_link(scanner, monkeypatch):
    calls = services(
        monkeypatch,
        phishtank=lambda r: httpx.Response(
            200, json={"results": {"in_database": True, "phish_id": 42, "verified": True, "valid": True}}
        ),
    )
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "https://example.com/login?email=me@example.org"}).json()
        got = client.post(f"/scans/{scan['id']}/compare", json={}).json()
    assert got["virustotal"]["status"] == "found"
    report = got["virustotal"]["report"]
    assert (report["engines"], report["stats"]["malicious"], report["reputation"]) == (2, 1, -5)
    assert [f["engine"] for f in report["flagged"]] == ["Alpha"]
    assert got["phishtank"] == got["phishtank"] | {"status": "listed", "phish_id": 42, "verified": True}
    # Personal data never leaves the scanner, and only a lookup was made (no fresh analysis).
    sent = [str(c.url) + c.content.decode() for c in calls]
    assert not any("me@example.org" in s or "me%40example.org" in s for s in sent)
    assert not any(c.method == "POST" and c.url.host == "www.virustotal.com" for c in calls)
    assert scanner and scanner[0][0] == scan["id"]


def test_a_fresh_analysis_is_only_asked_for_on_request(scanner, monkeypatch):
    def vt(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert parse_qs(request.content.decode())["url"] == ["https://example.com/"]
            return httpx.Response(200, json={"data": {"id": "an-1"}})
        if "/analyses/" in request.url.path:
            return httpx.Response(200, json={"data": {"attributes": {"status": "completed"}}})
        return httpx.Response(200, json=VT_REPORT)

    calls = services(monkeypatch, vt=vt)
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "https://example.com/"}).json()
        got = client.post(f"/scans/{scan['id']}/compare", json={"fresh": True}).json()
    assert got["virustotal"]["status"] == "found" and got["virustotal"]["fresh"] is True
    assert [c.method for c in calls if c.url.host == "www.virustotal.com"] == ["POST", "GET", "GET"]


def test_answers_that_are_not_reports_are_said_plainly(scanner, monkeypatch):
    services(
        monkeypatch,
        vt=lambda r: httpx.Response(404),
        phishtank=lambda r: httpx.Response(509),
    )
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "https://example.com/"}).json()
        got = client.post(f"/scans/{scan['id']}/compare", json={}).json()
    assert got["virustotal"]["status"] == "unknown"
    assert got["phishtank"]["status"] == "quota"


def test_a_broken_service_does_not_break_the_comparison(scanner, monkeypatch):
    services(monkeypatch, phishtank=lambda r: httpx.Response(500))
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "https://example.com/"}).json()
        got = client.post(f"/scans/{scan['id']}/compare", json={}).json()
    assert got["phishtank"]["status"] == "error" and got["virustotal"]["status"] == "found"


def test_a_link_to_a_private_address_is_never_sent(scanner, monkeypatch):
    calls = services(monkeypatch)
    scan = {
        "url": "http://localtest.me/",
        "visit": {"blocked": [{"host": "localtest.me", "reason": "local address (this machine)"}]},
    }
    import asyncio

    got = asyncio.run(compare.compare(scan, Settings(_env_file=None, virustotal_api_key="k"), fresh=False))
    assert got["virustotal"]["status"] == got["phishtank"]["status"] == "skipped"
    assert calls == []


def test_without_a_key_virustotal_says_so(scanner, monkeypatch):
    services(monkeypatch)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, virustotal_api_key="")
    with TestClient(app) as client:
        scan = client.post("/scan", json={"url": "https://example.com/"}).json()
        got = client.post(f"/scans/{scan['id']}/compare", json={}).json()
    assert got["virustotal"]["status"] == "not_configured"


def test_compare_needs_a_real_scan(scanner, monkeypatch):
    services(monkeypatch)
    with TestClient(app) as client:
        assert client.post("/scans/not-a-uuid/compare", json={}).status_code == 404
        missing = "00000000-0000-0000-0000-000000000000"
        assert client.post(f"/scans/{missing}/compare", json={}).status_code == 404
