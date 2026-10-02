"""Fingerprints: near-copies of a page must land close together, different pages far apart.
All pages here are made up for the tests."""

import base64
import io
import random
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app import fingerprint as fpm
from app.fingerprint import (
    Fingerprints,
    favicon_hash,
    fingerprint_visit,
    from_signed64,
    hamming,
    html_fingerprints,
    screenshot_phash,
    simhash,
    thumbnail,
    tlsh_distance,
    to_signed64,
)
from app.pages import COLUMNS, all_bands, band_values, page_row

PAGES = Path(__file__).parent / "fixtures" / "pages"


def kit_page(victim: str, token: str, extra: str = "") -> str:
    """A made-up phishing kit page. Each copy differs only in small per-victim details."""
    rows = "".join(
        f"<tr><td>Step {i}</td><td>Confirm detail number {i} to continue</td></tr>" for i in range(40)
    )
    return f"""<html><head><title>Secure account verification</title>
    <link rel="stylesheet" href="/static/{token}.css"></head><body>
    <div class="header"><img src="/logo.png" alt="logo"><h1>Verify your account</h1></div>
    <p>Dear customer {victim}, your account was limited because of unusual activity. Please confirm
    your details within 24 hours to restore full access to online banking services.</p>
    <form action="/submit.php?id={token}" method="post">
      <input name="username" placeholder="User ID"><input type="password" name="password">
      <input name="otp" placeholder="One time password"><button>Continue</button>
    </form><table>{rows}</table>{extra}
    <a href="https://help.example.org/contact">Help</a><a href="https://policy.example.net/privacy">Privacy</a>
    <div class="footer">Copyright 2026 Secure Banking Portal. All rights reserved.</div></body></html>"""


def other_page() -> str:
    words = "garden tomato recipe weather autumn harvest kitchen bread flour oven sunday market"
    rng = random.Random(7)
    paragraphs = "".join(
        f"<article><h2>Post {i}</h2><p>{' '.join(rng.choices(words.split(), k=40))}</p></article>"
        for i in range(25)
    )
    head = "<html><head><title>My cooking blog</title></head>"
    return f"{head}<body><nav><ul><li>Home</li></ul></nav>{paragraphs}</body></html>"


def picture(seed: int, tweak: bool = False) -> str:
    """A fake screenshot: colored blocks. `tweak` changes a small detail, like one line of text."""
    rng = random.Random(seed)
    image = Image.new("RGB", (640, 400), (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(image)
    for _ in range(12):
        x, y = rng.randrange(600), rng.randrange(360)
        draw.rectangle(
            [x, y, x + rng.randrange(20, 200), y + rng.randrange(20, 120)], fill=(rng.randrange(256),) * 3
        )
    if tweak:
        draw.rectangle([10, 10, 60, 16], fill=(255, 0, 0))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=70)
    return base64.b64encode(out.getvalue()).decode()


def test_copies_of_a_kit_are_close_and_other_pages_are_far():
    a = html_fingerprints(kit_page("Asha", "k81x"), "https://one.example.com/login")
    b = html_fingerprints(kit_page("Rahul", "p07q"), "https://two.example.com/login")
    c = html_fingerprints(other_page(), "https://blog.example.com/")

    assert a.dom_hash == b.dom_hash  # same structure, different words
    assert a.dom_hash != c.dom_hash
    assert hamming(a.dom_simhash, b.dom_simhash) == 0
    assert hamming(a.text_simhash, b.text_simhash) <= 6
    assert hamming(a.text_simhash, c.text_simhash) >= 18
    assert tlsh_distance(a.tlsh, b.tlsh) < 40
    assert tlsh_distance(a.tlsh, c.tlsh) > 150


def test_a_small_structural_change_moves_the_exact_hash_but_not_the_similarity_hash():
    a = html_fingerprints(kit_page("Asha", "k81x"))
    b = html_fingerprints(kit_page("Asha", "k81x", extra="<div><span>New banner</span></div>"))
    assert a.dom_hash != b.dom_hash
    assert hamming(a.dom_simhash, b.dom_simhash) <= 6


def test_terms_and_links_out():
    fp = html_fingerprints(kit_page("Asha", "k81x"), "https://one.example.com/login")
    assert "confirm" in fp.terms and "the" not in fp.terms
    assert len(fp.terms) <= fpm.MAX_TERMS
    # Other sites the page links to, by registered domain; its own site is left out.
    assert fp.out_domains == ["example.org", "example.net"]
    assert fp.tags > 80 and fp.words > 100


def test_scripts_and_styles_are_not_counted_as_words():
    html = (
        "<html><body><script>var secretword = 1;</script><style>.secretword{}</style>"
        + "<p>plain words here</p>" * 20
    )
    fp = html_fingerprints(html + "</body></html>")
    assert "secretword" not in fp.terms


@pytest.mark.parametrize("html", [None, "", "<p>hi</p>", "not html at all " * 2])
def test_tiny_or_missing_pages_give_empty_fingerprints(html):
    fp = html_fingerprints(html)
    assert fp.dom_hash is None and fp.text_simhash is None


def test_broken_html_never_raises():
    fp = html_fingerprints("<div><p>unclosed <b>tags" * 50 + "\x00\x01 <<>> </nope>")
    assert isinstance(fp, Fingerprints)


def test_test_pages_all_fingerprint():
    for path in PAGES.glob("*.html"):
        fp = html_fingerprints(path.read_text(encoding="utf-8"), "https://example.com/")
        assert fp.tags > 0, path.name


def test_simhash_needs_enough_material():
    assert simhash(["a", "b"]) is None
    assert len(simhash(["a", "b", "c", "d", "e"])) == 16
    assert hamming(None, "00") is None


def test_signed_round_trip_for_postgres():
    for hex_hash in (
        "0000000000000000",
        "7fffffffffffffff",
        "8000000000000000",
        "ffffffffffffffff",
        "f3a1b2c4d5e6f708",
    ):
        signed = to_signed64(hex_hash)
        assert -(1 << 63) <= signed < (1 << 63)
        assert from_signed64(signed) == hex_hash
    assert to_signed64(None) is None and from_signed64(None) is None


def test_screenshots_that_look_alike_hash_alike():
    a, b, c = (
        screenshot_phash(picture(1)),
        screenshot_phash(picture(1, tweak=True)),
        screenshot_phash(picture(2)),
    )
    assert hamming(a, b) <= 6
    assert hamming(a, c) >= 16


def test_blank_screenshots_get_no_hash():
    out = io.BytesIO()
    Image.new("RGB", (640, 400), (255, 255, 255)).save(out, "JPEG")
    assert screenshot_phash(base64.b64encode(out.getvalue()).decode()) is None
    assert screenshot_phash(None) is None
    assert screenshot_phash("not-base64-image") is None


def test_thumbnail_is_small():
    thumb = thumbnail(picture(3))
    assert thumb and len(thumb) < 12_000
    assert Image.open(io.BytesIO(thumb)).size[0] <= 240
    assert thumbnail(None) is None


def test_favicon_hash_matches_the_shodan_convention():
    icon = base64.b64encode(b"icon-bytes").decode()
    assert favicon_hash(icon) == favicon_hash(icon)
    assert favicon_hash(icon) != favicon_hash(base64.b64encode(b"other-icon").decode())
    assert -(1 << 31) <= favicon_hash(icon) < (1 << 31)
    assert favicon_hash(None) is None
    assert favicon_hash(base64.b64encode(b"x" * 300_000).decode()) is None  # too big to be an icon


def test_fingerprint_visit_combines_everything():
    visit = {
        "html": kit_page("Asha", "k81x"),
        "final_url": "https://one.example.com/login",
        "screenshot_jpeg_b64": picture(1),
        "favicon_b64": base64.b64encode(b"icon-bytes").decode(),
    }
    fp = fingerprint_visit(visit)
    assert fp.tlsh and fp.dom_hash and fp.phash and fp.favicon_hash is not None


def test_bands_find_near_copies():
    a = html_fingerprints(kit_page("Asha", "k81x"))
    b = html_fingerprints(kit_page("Rahul", "p07q"))
    c = html_fingerprints(other_page())
    assert set(all_bands(a)) & set(all_bands(b))
    assert not set(all_bands(a)) & set(all_bands(c))
    assert len(band_values("dom", a.dom_simhash)) == 4
    assert all(0 <= v < (1 << 31) for v in all_bands(a))
    assert band_values("phash", None) == []


def test_page_row_has_every_column_and_no_personal_data():
    fp = html_fingerprints(kit_page("Asha", "k81x"), "https://one.example.com/login")
    recon = {
        "server": {
            "status": "ok",
            "ip": "93.184.215.14",
            "asn": 15133,
            "as_org": "Example",
            "country_code": "US",
        },
        "registration": {
            "registrar": "Example Registrar",
            "created": "2026-09-30T10:00:00Z",
            "nameservers": ["B.NS.example.", "a.ns.example"],
        },
        "cert_history": {"other_domains": ["sibling.example.com"]},
        "certificate": {"names": ["one.example.com", "sibling.example.com"]},
    }
    row = page_row(
        source="scan",
        source_ref="abc",
        url="https://one.example.com/login?email=me@example.com",
        fp=fp,
        recon=recon,
    )
    assert list(row) == COLUMNS
    assert "me@example.com" not in row["url"]
    assert row["host"] == "one.example.com"
    assert row["ns_key"] == "a.ns.example,b.ns.example"
    assert row["domain_created"] == "2026-09-30"
    assert row["cert_domains"] == ["sibling.example.com", "one.example.com"]
    assert row["bands"] == all_bands(fp)


def test_non_english_words_survive():
    html = "<html><body>" + "<p>अपना खाता सत्यापित करें для входа введите пароль</p>" * 10 + "</body></html>"
    fp = html_fingerprints(html)
    assert "пароль" in fp.terms and "सत्यापित" in fp.terms  # vowel signs stay inside the word
    assert all("Ð" not in t for t in fp.terms)
