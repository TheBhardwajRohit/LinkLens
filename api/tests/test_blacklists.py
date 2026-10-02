"""Blacklist checks. Every outside service is a fake here: a small HTTP stand-in answers the way the
real one is documented to. Only reserved example names are used, never real scam links."""

import json

import httpx
import pytest

from app import blacklists
from app.analysis import analyze
from app.analysis.lexical import looks_random
from app.analysis.score import blacklist_reasons
from app.blacklists import http, safebrowsing, urlhaus, urlscan, virustotal
from app.blacklists.lists import KnownLists, host_keys, link_keys
from app.blacklists.models import Blacklists, SourceResult
from app.config import Settings

pytestmark = [pytest.mark.anyio, pytest.mark.real_blacklists]

BAD = "https://bad.example/login"
GOOD = "https://good.example/"


@pytest.fixture
def service(monkeypatch):
    """Install a fake for the outside world. Returns the list of requests it received."""
    calls: list[httpx.Request] = []

    def install(handler):
        def record(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        monkeypatch.setattr(http, "transport", httpx.MockTransport(record))
        return calls

    return install


# ---------- Google Safe Browsing ----------


async def test_safe_browsing_without_a_key_says_so(service):
    calls = service(lambda r: httpx.Response(500))
    got = await safebrowsing.check([BAD], "")
    assert got.status == "not_configured"
    assert calls == []


async def test_safe_browsing_lists_a_phishing_link_and_keeps_the_key_out_of_the_address(service):
    def google(request):
        body = json.loads(request.content)
        assert body["threatInfo"]["threatEntries"] == [{"url": BAD}, {"url": GOOD}]
        match = {"threatType": "SOCIAL_ENGINEERING", "threat": {"url": BAD}, "cacheDuration": "300s"}
        return httpx.Response(200, json={"matches": [match]})

    calls = service(google)
    got = await safebrowsing.check([BAD, GOOD], "secret-key")
    assert got.status == "listed"
    assert got.threats == ["phishing"]
    assert got.matched == [BAD]
    assert "suspected phishing" in got.note
    assert "secret-key" not in str(calls[0].url)
    assert calls[0].headers["x-goog-api-key"] == "secret-key"


async def test_safe_browsing_empty_reply_means_not_listed_and_is_cached(service):
    calls = service(lambda r: httpx.Response(200, json={}))
    first = await safebrowsing.check([GOOD], "k")
    again = await safebrowsing.check([GOOD], "k")
    assert first.status == again.status == "clean"
    assert len(calls) == 1
    assert again.cached is True and first.cached is False


@pytest.mark.parametrize(("code", "status"), [(429, "quota"), (403, "error"), (400, "error")])
async def test_safe_browsing_problems_get_a_plain_status(service, code, status):
    service(lambda r: httpx.Response(code, json={"error": {}}))
    got = await safebrowsing.check([GOOD], "k")
    assert got.status == status
    assert got.note


# ---------- VirusTotal ----------


def vt_reply(malicious: int, suspicious: int = 0):
    stats = {"malicious": malicious, "suspicious": suspicious, "harmless": 60, "undetected": 30}
    return httpx.Response(200, json={"data": {"attributes": {"last_analysis_stats": stats}}})


def test_virustotal_link_id_is_unpadded_base64():
    assert virustotal.url_id("https://example.com/") == "aHR0cHM6Ly9leGFtcGxlLmNvbS8"


async def test_virustotal_counts_vendors(service):
    calls = service(lambda r: vt_reply(7))
    got = await virustotal.check([BAD], "k")
    assert got.status == "listed"
    assert got.detail == {"malicious": 7, "suspicious": 0, "vendors": 97}
    assert "7 of 97" in got.note
    assert calls[0].headers["x-apikey"] == "k"
    assert calls[0].method == "GET"  # lookups only, never a submission


async def test_virustotal_one_flag_is_not_a_listing(service):
    service(lambda r: vt_reply(1))
    got = await virustotal.check([BAD], "k")
    assert got.status == "info"
    assert "false alarms" in got.note


async def test_virustotal_unknown_clean_and_refused(service):
    service(lambda r: httpx.Response(404, json={"error": {"code": "NotFoundError"}}))
    assert (await virustotal.check([BAD], "k")).status == "unknown"
    service(lambda r: vt_reply(0))
    assert (await virustotal.check([GOOD], "k")).status == "clean"
    service(lambda r: httpx.Response(401))
    assert (await virustotal.check(["https://other.example/"], "k")).status == "error"
    assert (await virustotal.check([BAD], "")).status == "not_configured"


async def test_virustotal_stays_inside_four_requests_a_minute(service):
    calls = service(lambda r: vt_reply(0))
    for i in range(4):
        await virustotal.check([f"https://site{i}.example/"], "k")
    fifth = await virustotal.check(["https://site5.example/"], "k")
    assert fifth.status == "quota"
    assert len(calls) == 4
    # A cached link costs no request, so it still answers.
    assert (await virustotal.check(["https://site0.example/"], "k")).status == "clean"


# ---------- URLhaus ----------


async def test_urlhaus_lists_a_live_malware_link(service):
    def haus(request):
        assert request.headers["Auth-Key"] == "k"
        assert b"url=" in request.content
        return httpx.Response(
            200,
            json={
                "query_status": "ok",
                "url_status": "online",
                "threat": "malware_download",
                "tags": ["elf", "mirai"],
                "urlhaus_reference": "https://urlhaus.abuse.ch/url/1/",
            },
        )

    service(haus)
    got = await urlhaus.check([BAD], "k")
    assert got.status == "listed"
    assert got.threats == ["malware"]
    assert "live right now" in got.note


async def test_urlhaus_falls_back_to_the_host(service):
    def haus(request):
        if request.url.path == "/v1/url/":
            return httpx.Response(200, json={"query_status": "no_results"})
        urls = [{"url_status": "offline"}, {"url_status": "offline"}]
        return httpx.Response(200, json={"query_status": "ok", "url_count": "2", "urls": urls})

    service(haus)
    got = await urlhaus.check([BAD], "k")
    assert got.status == "info"
    assert "2 malware links" in got.note


async def test_urlhaus_clean_refused_and_not_configured(service):
    service(lambda r: httpx.Response(200, json={"query_status": "no_results"}))
    assert (await urlhaus.check([GOOD], "k")).status == "clean"
    service(lambda r: httpx.Response(403))
    assert (await urlhaus.check(["https://other.example/"], "k")).status == "error"
    assert (await urlhaus.check([GOOD], "")).status == "not_configured"


# ---------- urlscan.io ----------


async def test_urlscan_reports_history_without_a_key(service):
    def scan(request):
        assert request.url.params["q"] == 'page.domain:"bad.example"'
        assert "API-Key" not in request.headers
        results = [{"task": {"time": "2026-09-30T10:00:00.000Z"}}]
        return httpx.Response(200, json={"total": 12, "results": results})

    calls = service(scan)
    got = await urlscan.check("bad.example", "")
    assert got.status == "info"
    assert got.note == "Scanned 12 times on urlscan.io, most recently on 30 Sep 2026."
    assert len(calls) == 1  # no verdict search without an account


async def test_urlscan_with_a_key_can_see_malicious_verdicts(service):
    def scan(request):
        flagged = "verdicts.malicious:true" in request.url.params["q"]
        total = 3 if flagged else 12
        return httpx.Response(
            200, json={"total": total, "results": [{"task": {"time": "2026-09-30T10:00:00Z"}}]}
        )

    service(scan)
    got = await urlscan.check("bad.example", "k")
    assert got.status == "listed"
    assert "3 of those scans were judged malicious" in got.note


async def test_urlscan_never_seen_and_quota(service):
    service(lambda r: httpx.Response(200, json={"total": 0, "results": []}))
    assert (await urlscan.check("new.example", "")).status == "unknown"
    service(lambda r: httpx.Response(429))
    assert (await urlscan.check("other.example", "")).status == "quota"


# ---------- Phishing.Database lists ----------


@pytest.fixture
def lists(tmp_path):
    (tmp_path / "phishing-database-links.txt").write_text(
        "http://bad.example/login.php\nhttps://Shop.Example/pay/?id=7\n", encoding="utf-8"
    )
    (tmp_path / "phishing-database-domains.txt").write_text(
        "example.net\nscam.github.io\nwww.example.org\n", encoding="utf-8"
    )
    known = KnownLists(tmp_path)
    known.load()
    return known


def test_link_and_host_forms():
    assert link_keys("https://Bad.Example/a/b/?x=1") == ["bad.example/a/b?x=1", "bad.example/a/b"]
    assert host_keys("a.b.example.net") == ["a.b.example.net", "b.example.net", "example.net"]
    # An ending that isn't on the public suffix list still stops at the last two labels.
    assert host_keys("a.b.evil.example") == ["a.b.evil.example", "b.evil.example", "evil.example"]
    # A free-hosting platform is never matched as a whole, only the one site on it.
    assert host_keys("scam.github.io") == ["scam.github.io"]


def test_lists_match_exact_links_whatever_the_scheme_or_extra_query(lists):
    assert lists.check(["https://bad.example/login.php?session=REDACTED"]).detail == {"match": "link"}
    assert lists.check(["http://shop.example/pay?id=7"]).status == "listed"
    assert lists.check(["http://shop.example/pay?id=8"]).status == "clean"


def test_lists_match_a_domain_and_its_subdomains(lists):
    got = lists.check(["https://login.example.net/x"])
    assert got.status == "listed"
    assert got.detail["match"] == "domain" and got.detail["domain"] == "example.net"
    assert lists.check(["https://example.org/"]).status == "clean"  # only www.example.org is listed
    assert lists.check(["https://scam.github.io/"]).status == "listed"
    assert lists.check(["https://other.github.io/"]).status == "clean"


def test_lists_not_loaded_yet_is_said_plainly(tmp_path):
    got = KnownLists(tmp_path).check([BAD])
    assert got.status == "skipped"
    assert "haven't been downloaded" in got.note


def test_clean_note_gives_the_list_sizes(lists):
    assert lists.check([GOOD]).note == "Not among 2 phishing links and 3 phishing domains."


# ---------- all together ----------


def test_links_to_check_removes_personal_data_and_private_stops():
    visit = {
        "hops": [
            {"url": "https://short.example/x?email=me@example.com"},
            {"url": "http://10.0.0.5/admin", "blocked": True},
            {"url": "https://final.example/login"},
        ],
        "final_url": "https://final.example/login",
    }
    got = blacklists.links_to_check("https://short.example/x?email=me@example.com", visit)
    assert got == ["https://short.example/x?email=REDACTED", "https://final.example/login"]


async def test_every_source_ends_with_a_status_even_when_things_break(service, monkeypatch):
    def world(request):
        if request.url.host == "safebrowsing.googleapis.com":
            match = {"threatType": "MALWARE", "threat": {"url": BAD}, "cacheDuration": "300s"}
            return httpx.Response(200, json={"matches": [match]})
        raise httpx.ConnectError("down")

    service(world)
    settings = Settings(
        _env_file=None, google_safe_browsing_api_key="k", virustotal_api_key="k", database_url=""
    )
    got = await blacklists.check([BAD], settings)
    by_id = {s.id: s.status for s in got.sources}
    assert by_id == {
        "safe_browsing": "listed",
        "phishing_database": "skipped",
        "virustotal": "error",
        "urlhaus": "not_configured",
        "urlscan": "error",
        "linklens": "skipped",
    }
    assert got.listed_by == ["Google Safe Browsing"]
    assert all(s.note for s in got.sources if s.status in ("error", "not_configured"))


# ---------- scoring ----------


def listed(source_id: str, name: str, **extra) -> dict:
    src = SourceResult(id=source_id, name=name, status="listed", **extra)
    return Blacklists(sources=[src], listed_by=[name]).model_dump()


def test_a_safe_browsing_listing_alone_makes_a_link_dangerous():
    visit = {"final_url": "https://plain.example/", "hops": [], "html": "<p>hello</p>"}
    found = listed("safe_browsing", "Google Safe Browsing", threats=["phishing"])
    got = analyze(visit, {}, "https://plain.example/", found)
    assert got.verdict == "dangerous"
    assert got.listed_by == ["Google Safe Browsing"]
    assert got.reasons[0].text == "Google Safe Browsing lists this link as suspected phishing."
    assert got.summary == "Google Safe Browsing lists this link as unsafe. Don't open it."


def test_a_malware_listing_sets_the_scam_type():
    visit = {"final_url": "https://plain.example/", "hops": [], "html": "<p>hello</p>"}
    found = listed("urlhaus", "URLhaus (abuse.ch)", threats=["malware"], detail={"url_status": "online"})
    got = analyze(visit, {}, "https://plain.example/", found)
    assert got.scam_type and got.scam_type.id == "malware"
    assert got.score >= 70


def test_listing_points():
    def points(source_id, status="listed", **detail):
        src = {"id": source_id, "status": status, "detail": detail, "threats": ["phishing"]}
        return [r.points for r in blacklist_reasons({"sources": [src]})]

    assert points("phishing_database", match="link") == [60]
    assert points("phishing_database", match="domain") == [45]
    assert points("phishing_database", match="domain", popular=True) == [15]
    assert points("virustotal", malicious=3, vendors=90) == [35]
    assert points("virustotal", malicious=9, vendors=90) == [60]
    assert points("virustotal", status="info") == [10]
    assert points("urlhaus", url_status="offline") == [45]
    assert points("safe_browsing", status="clean") == []
    assert blacklist_reasons(None) == []


@pytest.mark.parametrize("name", ["sbi-kyc-update", "secure-login-verify", "paypal-accountverification"])
def test_readable_names_are_not_called_random(name):
    assert looks_random(name) is False


@pytest.mark.parametrize("name", ["xk7qz9vbt2mw", "a8f3k2m9x1q7z5", "qwrtzpsdfghjk"])
def test_machine_made_names_are_called_random(name):
    assert looks_random(name) is True
