"""Full visits in the real sandbox browser, against the local fixture server only."""

import base64

import pytest

from app.visit import Limits, detect_bot_check, find_meta_refresh, visit

pytestmark = pytest.mark.anyio

FAST = Limits(nav_timeout_s=10, settle_deadline_s=15, hard_timeout_s=30)


def kinds(result):
    return [h.kind for h in result.hops]


async def test_plain_page(guard, fixture_server):
    r = await visit(fixture_server.url("/plain"), guard, FAST)
    assert r.stopped is None
    assert r.title == "Plain page"
    assert r.final_url == fixture_server.url("/plain")
    assert r.status == 200
    assert kinds(r) == ["start"]
    assert base64.b64decode(r.screenshot_jpeg_b64)[:2] == b"\xff\xd8"  # a real JPEG
    assert "Hello from the fixture server" in r.html
    assert r.contacted_domains == ["site.test"]


async def test_server_redirects(guard, fixture_server):
    r = await visit(fixture_server.url("/r302"), guard, FAST)
    assert kinds(r) == ["start", "server", "server"]
    assert [h.status for h in r.hops] == [302, 301, 200]
    assert r.final_url == fixture_server.url("/plain")


async def test_meta_refresh(guard, fixture_server):
    r = await visit(fixture_server.url("/meta"), guard, FAST)
    assert kinds(r) == ["start", "meta"]
    assert r.final_url == fixture_server.url("/plain")


async def test_script_redirect(guard, fixture_server):
    r = await visit(fixture_server.url("/js"), guard, FAST)
    assert kinds(r) == ["start", "script"]
    assert r.final_url == fixture_server.url("/plain")


async def test_refresh_header(guard, fixture_server):
    r = await visit(fixture_server.url("/refresh-header"), guard, FAST)
    assert kinds(r) == ["start", "header"]
    assert r.final_url == fixture_server.url("/plain")


async def test_form_submitted_by_the_page_itself(guard, fixture_server):
    r = await visit(fixture_server.url("/autoform"), guard, FAST)
    assert kinds(r) == ["start", "form"]
    assert r.final_url == fixture_server.url("/plain?q=1")


async def test_mixed_chain(guard, fixture_server):
    # 302 -> meta refresh -> script -> final page
    r = await visit(fixture_server.url("/mixed-chain"), guard, FAST)
    assert kinds(r) == ["start", "server", "meta", "script"]
    assert r.final_url == fixture_server.url("/plain")


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/to-private", "private network address"),
        ("/to-metadata", "cloud metadata address"),
        ("/to-rebind", "local address (this machine)"),
        ("/js-to-private", "private network address"),
        ("/js-to-rebind", "local address (this machine)"),
    ],
)
async def test_redirects_to_private_addresses_are_blocked(guard, fixture_server, path, reason):
    r = await visit(fixture_server.url(path), guard, FAST)
    assert r.stopped == "blocked"
    assert r.hops[-1].blocked
    assert r.hops[-1].reason == reason
    assert any(b.reason == reason for b in r.blocked)
    assert r.screenshot_jpeg_b64 is None  # no screenshot of an error page
    assert "LinkLens only visits public websites" in r.notes[0]


async def test_redirect_to_a_non_web_port_is_blocked(guard, fixture_server):
    r = await visit(fixture_server.url("/to-ssh"), guard, FAST)
    assert r.stopped == "blocked"
    assert "port 22" in r.hops[-1].reason


async def test_private_images_are_blocked_but_page_still_loads(guard, fixture_server):
    r = await visit(fixture_server.url("/images"), guard, FAST)
    assert r.stopped is None
    assert r.title == "Images"
    reasons = {b.host: b.reason for b in r.blocked}
    assert reasons["10.0.0.1"] == "private network address"
    assert reasons["169.254.169.254"] == "cloud metadata address"
    assert r.screenshot_jpeg_b64


async def test_first_address_private_never_starts_a_browser(guard):
    r = await visit("http://10.0.0.1/", guard, FAST)
    assert r.stopped == "blocked"
    assert r.duration_ms < 1000


async def test_unknown_domain_is_unreachable(guard):
    r = await visit("http://does-not-exist.test/", guard, FAST)
    assert r.stopped == "unreachable"


async def test_forms_are_never_submitted(guard, fixture_server):
    fixture_server.posts.clear()
    r = await visit(fixture_server.url("/form"), guard, FAST)
    assert r.title == "Login"
    assert fixture_server.posts == []


async def test_downloads_are_never_saved(guard, fixture_server):
    r = await visit(fixture_server.url("/download"), guard, FAST)
    assert r.stopped == "download"
    assert r.screenshot_jpeg_b64 is None


async def test_bot_check_is_detected_not_bypassed(guard, fixture_server):
    r = await visit(fixture_server.url("/captcha"), guard, FAST)
    assert r.bot_check == "reCAPTCHA"
    assert any("never try to get past" in n for n in r.notes)


async def test_popups_are_closed(guard, fixture_server):
    r = await visit(fixture_server.url("/popup"), guard, FAST)
    assert r.title == "Popup"
    assert any("popup" in n for n in r.notes)


async def test_dialogs_are_dismissed(guard, fixture_server):
    r = await visit(fixture_server.url("/alert"), guard, FAST)
    assert r.final_url == fixture_server.url("/plain")


async def test_slow_page_times_out(guard, fixture_server):
    r = await visit(
        fixture_server.url("/slow"), guard, Limits(nav_timeout_s=2, settle_deadline_s=3, hard_timeout_s=10)
    )
    assert r.stopped == "timeout"
    assert r.duration_ms < 10_000


async def test_late_meta_refresh_is_reported(guard, fixture_server):
    r = await visit(fixture_server.url("/meta-later"), guard, FAST)
    assert r.pending_refresh == fixture_server.url("/plain")


async def test_non_web_scheme_is_refused(guard):
    r = await visit("file:///etc/passwd", guard, FAST)
    assert r.stopped == "error"


def test_find_meta_refresh_variants():
    assert find_meta_refresh('<meta http-equiv="refresh" content="0;url=/next">') == "/next"
    assert (
        find_meta_refresh("<META CONTENT='5; URL=https://x.test/a' HTTP-EQUIV='Refresh'>")
        == "https://x.test/a"
    )
    assert find_meta_refresh('<meta http-equiv=refresh content="3">') == ""
    assert find_meta_refresh('<meta name="viewport" content="width=device-width">') is None


def test_detect_bot_check():
    assert (
        detect_bot_check('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js">', [])
        == "Cloudflare challenge"
    )
    assert detect_bot_check("", ["https://newassets.hcaptcha.com/captcha/v1/x"]) == "hCaptcha"
    assert detect_bot_check("<h1>hello</h1>", []) is None
