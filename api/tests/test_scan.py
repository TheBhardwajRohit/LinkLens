import pytest
from fastapi.testclient import TestClient

from app import sandbox_client
from app.main import app
from app.urls import UrlError, normalize_url

# Only safe, reserved example domains here. Tests never touch real scam links.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com/login", "https://example.com/login"),
        ("example.com", "https://example.com"),
        ("  example.com/path?q=1  ", "https://example.com/path?q=1"),
        ("HTTP://example.com", "http://example.com"),
        ("hxxps://example[.]com/login", "https://example.com/login"),
        ("hxxp://sub(.)example[.]org", "http://sub.example.org"),
        ("https://paypal.com@example.com/", "https://paypal.com@example.com/"),
        ("https://8.8.8.8/", "https://8.8.8.8/"),
        ("example.com:8443/x", "https://example.com:8443/x"),
    ],
)
def test_normalize_accepts(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "javascript:alert(1)",
        "data:text/html,hi",
        "file:///etc/passwd",
        "ftp://example.com",
        "mailto:someone@example.com",
        "localhost",
        "http://localhost:8000",
        "http://app.localhost",
        "http://127.0.0.1",
        "http://10.0.0.5/admin",
        "http://192.168.1.1",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fd00::1]/",
        "intranet",
        "https://example.com:99999/",
        "https://" + "a" * 2050 + ".com",
    ],
)
def test_normalize_rejects(raw):
    with pytest.raises(UrlError):
        normalize_url(raw)


FAKE_VISIT = {
    "requested_url": "https://example.com/login",
    "final_url": "https://example.com/login",
    "hops": [{"url": "https://example.com/login", "kind": "start", "status": 200, "blocked": False}],
    "screenshot_jpeg_b64": "abc",
    "html": "<script>evil()</script>",
    "stopped": None,
}


@pytest.fixture
def fake_sandbox(monkeypatch):
    calls = []

    async def fake_visit(sandbox_url, url):
        calls.append(url)
        return dict(FAKE_VISIT)

    monkeypatch.setattr(sandbox_client, "visit", fake_visit)
    return calls


def test_scan_sends_the_cleaned_link_to_the_sandbox(fake_sandbox):
    resp = TestClient(app).post("/scan", json={"url": "example.com/login"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://example.com/login"
    assert body["id"]
    assert fake_sandbox == ["https://example.com/login"]
    assert body["visit"]["screenshot_jpeg_b64"] == "abc"


def test_scan_never_passes_captured_html_to_the_website(fake_sandbox):
    body = TestClient(app).post("/scan", json={"url": "example.com"}).json()
    assert "html" not in body["visit"]
    assert "evil()" not in str(body)


def test_bad_links_never_reach_the_sandbox(fake_sandbox):
    TestClient(app).post("/scan", json={"url": "http://169.254.169.254/"})
    assert fake_sandbox == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (sandbox_client.SandboxUnavailable, "isn't running"),
        (sandbox_client.SandboxBusy, "busy"),
    ],
)
def test_sandbox_problems_give_a_plain_503(monkeypatch, error, message):
    async def broken_visit(sandbox_url, url):
        raise error

    monkeypatch.setattr(sandbox_client, "visit", broken_visit)
    resp = TestClient(app).post("/scan", json={"url": "example.com"})
    assert resp.status_code == 503
    assert message in resp.json()["detail"]


def test_scan_rejects_a_bad_link_with_a_plain_message():
    resp = TestClient(app).post("/scan", json={"url": "javascript:alert(1)"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Only http and https links can be scanned."


def test_scan_rejects_oversized_body():
    resp = TestClient(app).post("/scan", json={"url": "a" * 5000})
    assert resp.status_code == 422
