"""Family grouping on a small made-up library: three kits, a common template, and loose pages."""

import random
from datetime import UTC, datetime, timedelta

from app.fingerprint import html_fingerprints
from app.pages import all_bands
from app.similarity import Prints, from_hex
from jobs import cluster

DAY0 = datetime(2026, 9, 1, tzinfo=UTC)


def kit(kind: str, victim: str, token: str) -> str:
    """Made-up scam kits. Copies of one kit differ only in small per-victim details."""
    if kind == "bank":
        rows = "".join(f"<tr><td>Step {i}</td><td>Confirm banking detail {i}</td></tr>" for i in range(40))
        return (
            f"<html><head><title>Secure verification</title><link href='/{token}.css'></head><body>"
            f"<h1>Verify your account</h1><p>Dear {victim}, your net banking access is limited. Confirm"
            " your details within 24 hours to restore access to online banking.</p>"
            f"<form action='/s.php?id={token}'><input name='user'><input type='password' name='pass'>"
            f"<input name='otp'></form><table>{rows}</table><footer>Secure Portal</footer></body></html>"
        )
    if kind == "parcel":
        items = "".join(f"<li>Tracking update {i}: parcel waiting at the depot</li>" for i in range(35))
        return (
            "<html><head><title>Parcel on hold</title></head><body><div class='top'><img src='p.png'></div>"
            f"<h2>Delivery failed</h2><p>Hello {victim}, pay the customs fee to release parcel {token}.</p>"
            f"<ul>{items}</ul><form><input name='card'><input name='cvv'><input name='expiry'></form>"
            "<p>Courier support team</p></body></html>"
        )
    if kind == "wallet":
        cells = "".join(
            f"<div class='w'><span>Wallet {i}</span><button>Connect</button></div>" for i in range(30)
        )
        return (
            "<html><head><title>Connect wallet</title></head><body><header>Airdrop claim</header>"
            f"<section>{cells}</section><p>Session {token}: enter your recovery phrase to validate wallet"
            f" ownership, {victim}.</p><textarea name='seed'></textarea></body></html>"
        )
    # An ordinary blog theme that many honest sites use.
    posts = "".join(
        f"<article><h2>Post {i}</h2><p>Garden notes and recipes number {i}</p></article>" for i in range(30)
    )
    return (
        f"<html><head><title>{victim}'s blog</title></head><body><nav><a>Home</a><a>About</a></nav>"
        f"{posts}<footer>Powered by a common blog theme</footer></body></html>"
    )


def unique_page(seed: int) -> str:
    rng = random.Random(seed)
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november".split()
    tags = ["div", "p", "span", "section", "li", "h3", "blockquote", "em"]
    body = "".join(
        f"<{t}>{' '.join(rng.choices(words, k=rng.randrange(4, 14)))}</{t}>"
        for t in rng.choices(tags, k=rng.randrange(40, 90))
    )
    return f"<html><head><title>Page {seed}</title></head><body>{body}</body></html>"


def page(
    pid: int, html: str, site: str, label: str, brand=None, scam_type=None, day: int = 0
) -> cluster.Page:
    fp = html_fingerprints(html, f"https://{site}/")
    prints = Prints(
        fp.tlsh, fp.dom_hash, from_hex(fp.dom_simhash), from_hex(fp.text_simhash), None, None, fp.tags
    )
    return cluster.Page(pid, label, site, brand, scam_type, DAY0 + timedelta(days=day), prints, all_bands(fp))


def library() -> list[cluster.Page]:
    names = ["Asha", "Rahul", "Meera", "Vikram", "Sara", "Imran", "Divya", "Karan"]
    out: list[cluster.Page] = []
    pid = 100
    for i, n in enumerate(names):  # 8 copies of the bank kit on 8 sites
        out.append(
            page(pid, kit("bank", n, f"t{i}x9"), f"bank-{i}.example.com", "phish", "SBI", "banking", i)
        )
        pid += 1
    for i, n in enumerate(names[:5]):  # 5 copies of the parcel kit
        html = kit("parcel", n, f"IN{i}77")
        out.append(page(pid, html, f"parcel-{i}.example.net", "phish", "India Post", "government", i))
        pid += 1
    for i, n in enumerate(names[:4]):  # 4 wallet pages, all on ONE site
        out.append(page(pid, kit("wallet", n, f"s{i}"), "wallet.example.org", "phish", None, "crypto", i))
        pid += 1
    for i, n in enumerate(names[:6]):  # a blog theme on 6 honest sites, plus one scam page that copied it
        out.append(page(pid, kit("blog", n, "x"), f"blog-{i}.example.org", "benign"))
        pid += 1
    out.append(page(pid, kit("blog", "Mallory", "x"), "copycat.example.com", "phish"))
    pid += 1
    for i in range(12):  # unrelated pages
        out.append(page(pid, unique_page(i), f"other-{i}.example.com", "phish" if i % 2 else "benign"))
        pid += 1
    return out


def test_kits_become_families_and_everything_else_is_left_alone():
    lib = library()
    groups, compared = cluster.group(lib)
    found, templates = cluster.families(lib, groups)

    assert [(f.label, f.size, f.sites) for f in found] == [
        ("fake SBI banking page", 8, 8),
        ("fake India Post government notice", 5, 5),
    ]
    bank = found[0]
    assert bank.id == 100  # the oldest page's id, so the number stays the same night after night
    assert sorted(bank.members) == list(range(100, 108))
    assert bank.first_seen == DAY0 and bank.last_seen == DAY0 + timedelta(days=7)
    # The wallet pages sit on one site only, and the blog theme is mostly honest pages: no family.
    assert templates == 1
    assert compared < len(lib) * len(lib) / 2


def test_names():
    assert cluster.name("SBI", "banking") == "fake SBI banking page"
    assert cluster.name("PayPal", None) == "fake PayPal page"
    assert cluster.name(None, "credentials") == "login page with no clear brand"
    assert cluster.name(None, None) == "unnamed scam kit"


def test_a_brand_must_cover_half_the_scam_pages_to_name_the_family():
    assert cluster._top(["SBI", "SBI", "HDFC Bank", None], 0.5) == "SBI"
    assert cluster._top(["SBI", "HDFC Bank", "ICICI Bank", None], 0.5) is None
    assert cluster._top([None, None], 0.5) is None


def test_big_buckets_are_compared_without_the_quadratic_cost():
    lib = [page(i, kit("bank", f"victim{i}", f"tok{i}"), f"s{i}.example.com", "phish") for i in range(150)]
    groups, compared = cluster.group(lib)
    assert len({groups.find(i) for i in range(len(lib))}) == 1  # still one family
    assert compared < 150 * 149 / 2 / 4


def test_tiny_pages_never_start_a_family():
    lib = [
        page(i, "<html><body><p>Not found</p></body></html>", f"e{i}.example.com", "phish") for i in range(6)
    ]
    groups, _ = cluster.group(lib)
    found, _ = cluster.families(lib, groups)
    assert found == []
