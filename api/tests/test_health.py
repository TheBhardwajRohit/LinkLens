import pytest
from fastapi.testclient import TestClient

from app import checks
from app.config import Settings, get_settings
from app.main import app

FAKE_KEY = "test-secret-value-123"


@pytest.fixture
def client(monkeypatch):
    settings = Settings(_env_file=None, google_safe_browsing_api_key=FAKE_KEY)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(checks, "database", lambda url: "ok")
    monkeypatch.setattr(checks, "sandbox", lambda url: "ok")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_ok_when_all_services_up(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "sandbox": "ok"}


def test_health_degraded_when_a_service_is_down(client, monkeypatch):
    monkeypatch.setattr(checks, "database", lambda url: "unreachable")
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "unreachable"


def test_health_reports_key_names_but_never_values(client):
    resp = client.get("/health")
    keys = resp.json()["keys"]
    assert keys["google_safe_browsing"] is True
    assert keys["virustotal"] is False
    assert FAKE_KEY not in resp.text


def test_checks_never_raise_on_bad_targets():
    # Port 9 on localhost is closed, so both should fail fast and quietly.
    assert checks.database("postgresql://x:x@127.0.0.1:9/x") == "unreachable"
    assert checks.sandbox("http://127.0.0.1:9") == "unreachable"


def test_stats_reports_the_page_library(monkeypatch):
    from app import pages

    async def fake_stats(database_url):
        return {"pages": 12, "by_source": {"scan": {"phish": 2}}, "families": 1, "last_runs": []}

    monkeypatch.setattr(pages, "stats", fake_stats)
    body = TestClient(app).get("/stats").json()
    assert body["pages"] == 12
    assert body["by_source"] == {"scan": {"phish": 2}}


def test_stats_says_so_when_the_database_is_down(monkeypatch):
    from app import pages

    async def broken(database_url):
        raise ConnectionError("down")

    monkeypatch.setattr(pages, "stats", broken)
    resp = TestClient(app).get("/stats")
    assert resp.status_code == 503
    assert "can't be read" in resp.json()["detail"]
