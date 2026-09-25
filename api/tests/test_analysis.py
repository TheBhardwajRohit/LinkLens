"""Analysis tests: made-up pages and links only. Nothing here touches the network."""

from pathlib import Path

import pytest

from app.analysis import analyze
from app.analysis.content import analyze_page
from app.analysis.lexical import analyze_link, shannon_entropy
from app.analysis.toplist import toplist

PAGES = Path(__file__).parent / "fixtures" / "pages"


def page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def small_toplist(monkeypatch):
    monkeypatch.setattr(toplist, "ranks", {"github.com": 30, "icicidirect.com": 4200, "blogspot.com": 105})
    monkeypatch.setattr(toplist, "list_id", "TEST1")


# --- the link itself -------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "brand", "kind"),
    [
        ("https://paypa1.com/login", "PayPal", "typo"),
        ("https://www.hdcfbank.com/", "HDFC Bank", "typo"),
        ("https://xn--pypal-4ve.com/", "PayPal", "homograph"),
        ("https://sbi-kyc-update.com/", "SBI", "combo"),
        ("https://netflixaccountsupport.com/", "Netflix", "combo"),
        ("https://paypal.com.secure-login.xyz/", "PayPal", "subdomain"),
    ],
)
def test_lookalike_names(url, brand, kind):
    la = analyze_link(url).lookalike
    assert la is not None and (la.brand, la.kind) == (brand, kind)


@pytest.mark.parametrize(
    ("url", "brand"),
    [
        ("https://retail.onlinesbi.sbi/", "SBI"),
        ("https://www.hdfcbank.com/", "HDFC Bank"),
        ("https://paypal.com/", "PayPal"),
        ("https://www.incometax.gov.in/", "Income Tax Department"),
    ],
)
def test_real_brand_sites_are_recognized(url, brand):
    f = analyze_link(url)
    assert f.official_brand == brand
    assert f.lookalike is None


def test_popular_sites_containing_a_brand_name_are_not_lookalikes():
    assert analyze_link("https://www.icicidirect.com/").lookalike is None


def test_structure_tricks():
    f = analyze_link("http://user@93.184.215.14:8080/login//verify")
    assert f.is_ip and f.has_at and f.port == 8080 and f.double_slash_path
    assert "login" in f.url_words and "verify" in f.url_words


def test_free_hosting_counts_each_site_separately():
    f = analyze_link("https://sbi-rewards.blogspot.com/")
    assert f.free_hosting == "blogspot.com"
    assert f.site == "sbi-rewards.blogspot.com"
    assert f.tranco_rank is None  # blogspot.com is popular, this one site isn't


def test_shortener_and_abused_tld():
    assert analyze_link("https://bit.ly/3abc").shortener
    assert analyze_link("https://win-prize.xyz/").abused_tld


def test_entropy():
    assert shannon_entropy("aaaa") == 0
    assert shannon_entropy("x7kq9zp2mw4r") > 3.5


# --- the page --------------------------------------------------------------


def test_sbi_kyc_page_features():
    f = analyze_page(page("sbi_kyc.html"), "https://sbi-kyc-update.com/login")
    assert {"password", "otp", "netbanking"} <= set(f.asks_for)
    assert f.form_to_other_domain and f.form_targets == ["collect-data-example.ru"]
    assert "SBI" in f.brands_mentioned and "SBI" in f.brand_in_title
    assert f.right_click_blocked
    assert "urgency" in f.phrases
    assert f.empty_link_share > 0.5


def test_crypto_page_features():
    f = analyze_page(page("crypto_seed.html"), "https://wallet-sync.example.com/")
    assert "seed_phrase" in f.asks_for
    assert f.wallets == ["Ethereum"]


def test_benign_page_has_no_sensitive_fields():
    f = analyze_page(page("benign.html"), "https://lemon-cakes.example.com/")
    assert f.asks_for == []
    assert f.phrases == {}


def test_no_html_means_not_captured():
    assert analyze_page(None, None).captured is False


# --- the full verdict ------------------------------------------------------


def visit_for(url: str, html: str | None, **extra) -> dict:
    return {
        "requested_url": url,
        "final_url": url,
        "hops": [{"url": url, "kind": "start"}],
        "html": html,
        **extra,
    }


def recon(age_days: int | None = 400, trusted: bool = True) -> dict:
    return {
        "registration": {"status": "ok", "age_days": age_days, "flags": []},
        "dns": {"status": "ok"},
        "certificate": {
            "trusted": trusted,
            "problem": None if trusted else "The certificate is self-signed.",
        },
        "cert_history": {},
    }


@pytest.mark.parametrize(
    ("fixture", "url", "scam", "brand"),
    [
        ("sbi_kyc.html", "https://sbi-kyc-update.com/login", "banking", "SBI"),
        ("crypto_seed.html", "https://wallet-sync-example.com/", "crypto", None),
        ("prize.html", "https://lucky-draw-example.com/", "prize", None),
        ("tech_support.html", "https://pc-alert-example.com/", "tech_support", None),
        ("job.html", "https://earn-daily-example.com/", "job", None),
        ("echallan.html", "https://echallan-pay.example.com/", "government", "Parivahan (e-Challan)"),
        ("shop.html", "https://mega-sale-example.com/", "shop", None),
        ("malware.html", "https://browser-update-example.com/", "malware", None),
    ],
)
def test_scam_pages_get_the_right_type(fixture, url, scam, brand):
    a = analyze(visit_for(url, page(fixture)), recon(age_days=3), url)
    assert a.verdict in ("suspicious", "dangerous"), [r.text for r in a.reasons]
    assert a.scam_type is not None and a.scam_type.id == scam, a.scam_type
    if brand:
        assert a.scam_type.brand == brand


def test_fake_sbi_page_is_dangerous_with_plain_reasons():
    url = "https://sbi-kyc-update.com/login"
    a = analyze(visit_for(url, page("sbi_kyc.html")), recon(age_days=2, trusted=False), url)
    assert a.verdict == "dangerous" and a.score >= 70
    assert a.summary == "This looks like a fake SBI banking page."
    texts = " ".join(r.text for r in a.reasons)
    assert "only 2 days old" in texts
    assert "asks for a one-time password (OTP)" in texts
    assert "isn't SBI's real website" in texts
    assert a.reasons[0].points >= a.reasons[-1].points  # strongest first


def test_mentioning_other_brands_is_not_impersonation():
    html = "<title>Our partners</title><p>We work with Microsoft, Google and PayPal.</p>"
    url = "https://partners-blog-example.com/"
    a = analyze(visit_for(url, html), recon(age_days=900), url)
    assert not any("isn't" in r.text for r in a.reasons)
    assert a.verdict == "safe"


def test_harmless_old_page_is_safe():
    url = "https://lemon-cakes-example.com/"
    a = analyze(visit_for(url, page("benign.html")), recon(age_days=4000), url)
    assert a.verdict == "safe"
    assert a.scam_type is None
    assert any("existed for 10 years" in g.text for g in a.good_signs)


def test_popular_real_site_is_safe():
    url = "https://github.com/"
    a = analyze(visit_for(url, page("benign.html")), recon(age_days=6900), url)
    assert a.verdict == "safe" and a.score == 0
    assert any("most visited" in g.text for g in a.good_signs)


def test_link_to_private_address_is_flagged_even_without_a_page():
    url = "http://localtest.me/"
    old_domain = {"registration": {"status": "ok", "age_days": 5000, "flags": []}}
    a = analyze(visit_for(url, None, stopped="blocked"), old_domain, url)
    assert a.partial
    assert a.verdict == "suspicious"  # an old domain can't make this look safe
    assert "private address" in a.summary
    assert any("private or internal address" in r.text for r in a.reasons)


def test_download_counts_as_malware():
    url = "https://free-codec-example.xyz/get"
    a = analyze(visit_for(url, None, stopped="download", downloads=[url]), recon(age_days=5), url)
    assert a.verdict == "dangerous"
    assert a.scam_type is not None and a.scam_type.id == "malware"


def test_shortened_link_is_judged_by_where_it_lands():
    start, end = "https://bit.ly/3abc", "https://paypa1.com/signin"
    visit = visit_for(end, page("benign.html"))
    visit["requested_url"] = start
    visit["hops"] = [{"url": start, "kind": "start"}, {"url": end, "kind": "server"}]
    a = analyze(visit, recon(age_days=4), start)
    texts = [r.text for r in a.reasons]
    assert any("imitating PayPal" in t for t in texts)
    assert any("shortened" in t for t in texts)
