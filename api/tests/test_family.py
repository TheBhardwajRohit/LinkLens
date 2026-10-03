"""Family Finder and Sibling Hunter. The page library here is a handful of made-up rows; nothing
touches a database, DNS, or the internet except where a fake stands in."""

from datetime import UTC, datetime

import httpx
import pytest

from app import family, siblings
from app.analysis import analyze
from app.analysis.score import family_reasons
from app.blacklists import http
from app.fingerprint import html_fingerprints, to_signed64
from app.similarity import Prints, compare, describe, from_hex

pytestmark = [pytest.mark.anyio, pytest.mark.real_library]


def kit_page(victim: str, token: str, extra: str = "") -> str:
    rows = "".join(
        f"<tr><td>Step {i}</td><td>Confirm detail number {i} to continue</td></tr>" for i in range(40)
    )
    return (
        f"<html><head><title>Secure account verification</title><link href='/static/{token}.css'></head>"
        f"<body><h1>Verify your account</h1><p>Dear customer {victim}, your account was limited because of"
        " unusual activity. Please confirm your details within 24 hours to restore full access.</p>"
        f"<form action='/submit.php?id={token}'><input name='username'><input type='password' name='pw'>"
        f"<input name='otp'></form><table>{rows}</table>{extra}<footer>Secure Portal</footer></body></html>"
    )


def blog_page() -> str:
    posts = "".join(
        f"<article><h2>Post {i}</h2><p>Garden notes and bread recipes {i}</p></article>" for i in range(30)
    )
    return f"<html><head><title>A blog</title></head><body><nav><a>Home</a></nav>{posts}</body></html>"


def row(pid: int, html: str, site: str, label: str = "phish", family_id=None, thumb=False) -> tuple:
    """A page-library row, shaped like the query in family._candidates."""
    fp = html_fingerprints(html, f"https://{site}/login")
    return (
        pid,
        f"https://{site}/login?email=victim@example.com",
        site,
        label,
        "SBI" if label == "phish" else None,
        "Secure account verification",
        datetime(2026, 9, 3, tzinfo=UTC),
        fp.tlsh,
        fp.dom_hash,
        to_signed64(fp.dom_simhash),
        to_signed64(fp.text_simhash),
        None,
        None,
        fp.tags,
        family_id,
        thumb,
    )


def prints(html: str) -> Prints:
    fp = html_fingerprints(html)
    return Prints(
        fp.tlsh, fp.dom_hash, from_hex(fp.dom_simhash), from_hex(fp.text_simhash), None, None, fp.tags
    )


# ---------- similarity ----------


def test_copies_of_a_kit_match_and_unrelated_pages_do_not():
    a, b, c = prints(kit_page("Asha", "k81")), prints(kit_page("Rahul", "p07")), prints(blog_page())
    alike = compare(a, b)
    assert alike.match and alike.percent >= 90
    assert {"code", "structure", "words"} <= set(alike.kinds)
    assert not compare(a, c).match


def test_one_kind_of_agreement_is_never_enough():
    icon_only = compare(Prints(favicon=123, tags=50), Prints(favicon=123, tags=50))
    assert icon_only.kinds == ("icon",) and not icon_only.match
    same_structure_only = compare(
        Prints(dom_hash="aa", dom=1, text=0, tags=50),
        Prints(dom_hash="aa", dom=1, text=(1 << 40) - 1, tags=50),
    )
    assert not same_structure_only.match


def test_a_common_default_icon_counts_for_nothing():
    a = Prints(dom_hash="aa", dom=5, favicon=77, tags=50)
    assert "icon" in compare(a, a).kinds
    assert "icon" not in compare(a, a, frozenset({77})).kinds


def test_tiny_pages_need_more_to_match():
    small = Prints(dom_hash="aa", dom=5, text=9, tags=6)
    big = Prints(dom_hash="aa", dom=5, text=9, tags=60)
    assert compare(big, big).match
    assert not compare(small, small).match


def test_describe_reads_like_a_sentence():
    assert describe(("code",)) == "nearly the same code"
    assert describe(("code", "structure", "icon")) == (
        "nearly the same code, the same page structure and the same site icon"
    )
    assert describe(()) == ""


# ---------- family ----------


def test_rank_keeps_real_matches_closest_first_and_hides_personal_data():
    fp = html_fingerprints(kit_page("Asha", "k81"), "https://new-site.example.com/login")
    rows = [
        row(1, blog_page(), "blog.example.org", "benign"),
        row(
            2, kit_page("Rahul", "p07", "<div><b>banner</b><i>x</i></div>"), "old-b.example.net", family_id=7
        ),
        row(3, kit_page("Meera", "z33"), "old-a.example.net", family_id=7, thumb=True),
        row(4, kit_page("Self", "s00"), "new-site.example.com"),  # the scanned site itself
    ]
    found = family.rank(fp, rows, "new-site.example.com")
    assert [p.page_id for p in found] == [3, 2]
    assert all(p.percent >= 90 for p in found)  # ordered by how strongly the fingerprints agree
    assert found[0].has_thumb and found[0].family_id == 7
    assert "victim@example.com" not in found[0].url
    assert "same page structure" in found[0].alike


async def test_find_reports_a_family_match(monkeypatch):
    fp = html_fingerprints(kit_page("Asha", "k81"), "https://new-site.example.com/login")
    rows = [row(i, kit_page(f"v{i}", f"t{i}"), f"old-{i}.example.net", family_id=7) for i in range(1, 5)]

    async def candidates(database_url, prints_, own_ref):
        return rows, 56_000

    async def one_family(database_url, family_id):
        assert family_id == 7
        return family.Family(id=7, label="fake SBI banking page", brand="SBI", size=43, sites=30)

    monkeypatch.setattr(family, "_candidates", candidates)
    monkeypatch.setattr(family, "_family", one_family)
    got = await family.find("postgresql://x", fp, own_ref="abc", own_site="new-site.example.com")
    assert got.status == "matched"
    assert got.family.label == "fake SBI banking page" and got.family.percent >= 90
    assert got.note.startswith("Looks ") and "43 pages on 30 sites" in got.note
    assert got.scam_matches == 4 and got.library_size == 56_000


async def test_find_without_a_family_yet_still_reports_similar_scam_pages(monkeypatch):
    fp = html_fingerprints(kit_page("Asha", "k81"))

    async def candidates(database_url, prints_, own_ref):
        return [row(1, kit_page("Rahul", "p07"), "old.example.net")], 10

    monkeypatch.setattr(family, "_candidates", candidates)
    got = await family.find("postgresql://x", fp)
    assert got.status == "similar" and got.family is None
    assert "1 known scam page," in got.note


async def test_find_spots_a_copy_of_an_ordinary_site(monkeypatch):
    fp = html_fingerprints(kit_page("Asha", "k81"))

    async def candidates(database_url, prints_, own_ref):
        return [row(1, kit_page("Asha", "k81"), "realbank.example.org", "benign")], 10

    monkeypatch.setattr(family, "_candidates", candidates)
    got = await family.find("postgresql://x", fp, own_site="fake.example.com")
    assert got.status == "copy" and got.copied_site == "realbank.example.org"
    assert "realbank[.]example[.]org" in got.note


async def test_find_says_plainly_when_there_is_nothing_or_no_library(monkeypatch):
    fp = html_fingerprints(kit_page("Asha", "k81"))

    async def nothing(database_url, prints_, own_ref):
        return [], 500

    monkeypatch.setattr(family, "_candidates", nothing)
    assert (
        await family.find("postgresql://x", fp)
    ).note == "Nothing among 500 known pages looks like this one."
    assert (await family.find(None, fp)).status == "unavailable"
    assert (await family.find("postgresql://x", html_fingerprints(None))).status == "skipped"

    async def broken(database_url, prints_, own_ref):
        raise ConnectionError("down")

    monkeypatch.setattr(family, "_candidates", broken)
    assert (await family.find("postgresql://x", fp)).status == "unavailable"


# ---------- siblings ----------


def test_name_variants_cover_the_usual_tricks():
    variants = siblings.name_variants("sbi-kyc-update.com")
    assert "sbi-kyc-update.net" in variants  # another ending
    assert "sbi-kyc-updat.com" in variants  # a dropped letter
    assert "sbi-kyc-updates.com" in variants  # an added s
    assert "sbikycupdate.com" in variants  # hyphens removed
    assert "sbi-kyc-upd4te.com" in variants  # a look-alike character
    assert "sbi-kyc-update.com" not in variants  # never the name itself
    assert len(variants) <= siblings.MAX_LOOKALIKES
    assert all(not v.startswith("-") and "--" not in v for v in variants)
    assert siblings.name_variants("localhost") == []


async def test_lookalikes_keep_only_names_that_exist(monkeypatch):
    async def exists(resolver, name, limit):
        return name in ("sbi-kyc-update.net", "sbi-kyc-updates.com")

    monkeypatch.setattr(siblings, "_exists", exists)
    tab = await siblings.lookalikes("sbi-kyc-update.com")
    assert tab.status == "ok" and tab.total == 2
    assert [s.name for s in tab.items] == ["sbi-kyc-update.net", "sbi-kyc-updates.com"]
    assert "Existing doesn't mean scam" in tab.note

    async def none(resolver, name, limit):
        return False

    monkeypatch.setattr(siblings, "_exists", none)
    tab = await siblings.lookalikes("sbi-kyc-update.com")
    assert tab.status == "none" and tab.note.startswith("None of ")
    assert (await siblings.lookalikes("scam.github.io", free_hosting=True)).status == "skipped"
    assert (await siblings.lookalikes(None)).status == "skipped"


def test_certificate_neighbours():
    recon = {
        "cert_history": {"other_domains": ["Sibling-One.example.net"]},
        "certificate": {"names": ["*.own.example.com", "www.sibling-two.example.org", "own.example.com"]},
    }
    found = siblings._cert_neighbours(recon, "example.com")
    assert [s.name for s in found] == ["sibling-one.example.net", "example.org"]
    assert all(s.why == "on the same security certificate" for s in found)


async def test_same_owner_without_a_database_uses_the_certificate():
    recon = {
        "registered_domain": "own.example.com",
        "registration": {"registrant": "REDACTED FOR PRIVACY", "nameservers": ["ns1.example.net"]},
        "cert_history": {"other_domains": ["sibling.example.net"]},
    }
    tab = await siblings.same_owner(None, recon, "own.example.com")
    assert tab.status == "ok" and tab.items[0].name == "sibling.example.net"
    assert "hidden in the public record" in tab.note
    assert (await siblings.same_owner(None, {}, None)).status == "skipped"


async def test_same_server_on_a_shared_network_says_it_proves_little(monkeypatch):
    monkeypatch.setattr(http, "transport", httpx.MockTransport(lambda r: httpx.Response(500)))
    recon = {"server": {"ip": "104.20.23.154", "asn": 13335, "status": "ok"}}
    tab = await siblings.same_server(None, recon, "own.example.com", urlscan=True, urlscan_key="")
    assert tab.status == "none"
    assert "Cloudflare" in tab.note and "thousands of unrelated sites" in tab.note
    assert (await siblings.same_server(None, {}, None, urlscan=False, urlscan_key="")).status == "skipped"


async def test_same_server_lists_what_urlscan_has_seen_on_the_address(monkeypatch):
    def urlscan(request):
        assert request.url.params["q"] == 'page.ip:"93.184.215.14"'
        pages_seen = [
            {"page": {"apexDomain": d}}
            for d in ("own.example.com", "a.example.net", "a.example.net", "b.example.org")
        ]
        return httpx.Response(200, json={"results": pages_seen})

    monkeypatch.setattr(http, "transport", httpx.MockTransport(urlscan))
    recon = {"server": {"ip": "93.184.215.14", "asn": 64500, "status": "ok"}}
    tab = await siblings.same_server(None, recon, "own.example.com", urlscan=True, urlscan_key="")
    assert [s.name for s in tab.items] == ["a.example.net", "b.example.org"]
    assert tab.items[0].source == "urlscan"


def test_same_design_comes_from_the_family_matches():
    result = family.FamilyResult(
        status="similar",
        similar=[
            family.SimilarPage(
                page_id=1,
                url="https://a.example.net/x",
                site="a.example.net",
                label="phish",
                percent=96,
                alike="nearly the same code",
            ),
            family.SimilarPage(
                page_id=2, url="https://own.example.com/x", site="own.example.com", percent=99
            ),
        ],
    )
    tab = siblings.same_design(result, "own.example.com")
    assert [s.name for s in tab.items] == ["a.example.net"]
    assert tab.items[0].known_scam and tab.items[0].why == "96% alike: nearly the same code"
    assert (
        siblings.same_design(family.FamilyResult(status="unavailable", note="x"), None).status
        == "unavailable"
    )


# ---------- scoring ----------


def test_family_and_sibling_points():
    fam = {"status": "matched", "family": {"label": "fake SBI banking page", "size": 43, "percent": 96}}
    sib = {
        "same_server": {"items": [{"name": "a.example.net", "known_scam": True}], "note": None},
        "same_owner": {"items": [{"name": f"s{i}.example.net", "known_scam": True} for i in range(3)]},
    }
    got = family_reasons(fam, sib, trusted=False)
    assert [(r.points, r.area) for r in got] == [(40, "family"), (15, "family"), (25, "family")]
    assert got[0].text == 'It looks 96% like a known scam family ("fake SBI banking page", 43 pages).'
    assert got[1].text == "It shares its server address with 1 known scam site."
    # A brand's real site (or a very popular one) is never marked down for being copied by scammers.
    assert family_reasons(fam, sib, trusted=True) == []
    shared = {
        "same_server": {"items": sib["same_server"]["items"], "note": "serves thousands of unrelated sites"}
    }
    assert family_reasons(None, shared, trusted=False) == []
    assert (
        family_reasons({"status": "similar", "scam_matches": 2, "similar": [{"percent": 91}]}, None, False)[
            0
        ].points
        == 25
    )
    assert family_reasons({"status": "copy", "copied_site": "bank.example.org"}, None, False)[0].points == 20


def test_a_family_match_shows_up_in_the_verdict():
    visit = {"final_url": "https://plain.example.com/", "hops": [], "html": kit_page("Asha", "k81")}
    fam = {"status": "matched", "family": {"label": "fake SBI banking page", "size": 43, "percent": 96}}
    got = analyze(visit, {}, "https://plain.example.com/", None, fam, None)
    assert any("known scam family" in r.text for r in got.reasons)
    assert got.verdict != "safe"


def test_the_same_site_builder_skeleton_is_not_a_match_without_shared_content():
    # Two pages made with the same site builder: identical code and structure, different words.
    fp = html_fingerprints(kit_page("Asha", "k81"))
    one = Prints(fp.tlsh, "aa", 5, 0, None, None, 80)
    two = Prints(fp.tlsh, "aa", 5, (1 << 40) - 1, None, None, 80)
    alike = compare(one, two)
    assert alike.points >= 3 and set(alike.kinds) == {"code", "structure"}
    assert not alike.match
    # The same wording on top of that makes it a match.
    assert compare(one, one).match


def test_standard_notices_and_nearly_empty_pages_are_boilerplate():
    from app.similarity import boilerplate

    for title in ("Account Suspended", "404 Not Found", "Welcome to nginx!", "Index of /", "Domain for sale"):
        assert boilerplate(title, 200), title
    assert boilerplate("My shop", 5)  # almost no words
    assert not boilerplate("State Bank of India: KYC update", 200)
    assert not boilerplate(None, 200)


async def test_find_does_not_compare_boilerplate_pages(monkeypatch):
    async def never(database_url, prints_, own_ref):
        raise AssertionError("the library must not be searched for a boilerplate page")

    monkeypatch.setattr(family, "_candidates", never)
    fp = html_fingerprints(kit_page("Asha", "k81"))
    got = await family.find("postgresql://x", fp, title="Account Suspended")
    assert got.status == "skipped" and "standard notice" in got.note


async def test_a_free_hosted_site_has_no_owner_siblings_and_a_shared_server():
    """Every site on github.io shares GitHub's certificate, registration, and addresses."""
    from app import siblings as sib

    record = {
        "registered_domain": "github.io",
        "registration": {"registrant": "GitHub, Inc.", "registrar": "MarkMonitor", "created": "2013-03-08"},
        "certificate": {"names": ["*.github.io", "github.io", "*.githubusercontent.com"]},
        "server": {"ip": "185.199.108.153", "asn": 0, "status": "ok"},
    }
    owner = await sib.same_owner(None, record, "someone.github.io", free_hosting=True)
    assert owner.status == "skipped" and owner.items == []
    assert "free hosting service" in owner.note
    # Without the flag the shared certificate would have produced "siblings".
    assert (await sib.same_owner(None, record, "someone.github.io")).items
    server = await sib.same_server(
        None, record, "someone.github.io", urlscan=False, urlscan_key="", free_hosting=True
    )
    assert "thousands of unrelated sites" in server.note
