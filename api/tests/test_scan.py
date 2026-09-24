import pytest
from fastapi.testclient import TestClient

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


def test_scan_accepts_a_valid_link():
    resp = TestClient(app).post("/scan", json={"url": "example.com/login"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "received"
    assert body["url"] == "https://example.com/login"
    assert body["id"]


def test_scan_rejects_a_bad_link_with_a_plain_message():
    resp = TestClient(app).post("/scan", json={"url": "javascript:alert(1)"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Only http and https links can be scanned."


def test_scan_rejects_oversized_body():
    resp = TestClient(app).post("/scan", json={"url": "a" * 5000})
    assert resp.status_code == 422
