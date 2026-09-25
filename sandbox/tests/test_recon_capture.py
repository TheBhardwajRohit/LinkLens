"""The sandbox also captures what recon needs from the site itself: headers, IPs, and the certificate."""

import pytest

from app.guard import Blocked
from app.tls import fetch
from app.visit import visit
from tests.test_visit import FAST

pytestmark = pytest.mark.anyio


async def test_https_visit_reads_the_certificate(guard, fixture_server):
    r = await visit(fixture_server.https_url("/plain"), guard, FAST)
    assert r.stopped is None
    assert r.title == "Plain page"
    cert = r.tls
    assert cert is not None
    assert cert.subject == "site.test"
    assert cert.self_signed is True
    assert cert.trusted is False
    assert "self-signed" in cert.problem
    assert set(cert.names) == {"site.test", "www.site.test"}
    assert 28 <= cert.days_left <= 30
    assert len(cert.sha256) == 64


async def test_http_visit_has_no_certificate(guard, fixture_server):
    r = await visit(fixture_server.url("/plain"), guard, FAST)
    assert r.tls is None


async def test_headers_are_kept_but_cookie_values_are_not(guard, fixture_server):
    r = await visit(fixture_server.url("/cookie"), guard, FAST)
    assert r.headers["x-powered-by"] == "PHP/8.3"
    assert "secret-value" not in str(r.headers)
    assert r.headers["set-cookie"].startswith("1 cookie")


async def test_server_ip_is_the_one_actually_used(guard, fixture_server):
    r = await visit(fixture_server.url("/plain"), guard, FAST)
    assert r.server_ips == {"site.test": "127.0.0.1"}


async def test_certificate_fetch_goes_through_the_guard(guard):
    with pytest.raises(Blocked):
        await fetch("10.0.0.1", 443, guard)
