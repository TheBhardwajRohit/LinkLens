"""The real-site check: what is kept from a scan, and how the saved pages are rated."""

import json
from pathlib import Path

import pytest

from app.analysis.score import MODEL_ALONE_MAX
from app.analysis.toplist import toplist
from app.library import digest_page
from app.ml.features import NAMES
from app.ml.model import TreeModel
from jobs import honest_check

PAGES = Path(__file__).parent.parent.parent / "api" / "tests" / "fixtures" / "pages"
BENIGN = (PAGES / "benign.html").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def small_toplist(monkeypatch):
    monkeypatch.setattr(toplist, "ranks", {"github.com": 30})


def scan_of(url: str, html: str, reasons=(), good=(), bot_check=None, rule_score=0, backing=None) -> dict:
    """A scan result shaped like the scan server's reply, built from a page the way a scan reads it."""
    d = digest_page(url, html)
    return {
        "visit": {"bot_check": bot_check},
        "analysis": {
            "link": d.link.model_dump(mode="json"),
            "final_link": None,
            "page": d.page.model_dump(mode="json"),
            "reasons": [{"points": p, "area": a, "text": "x"} for p, a in reasons],
            "good_signs": [{"points": p, "area": a, "text": "x"} for p, a in good],
            "rule_score": rule_score,
            "backing": rule_score if backing is None else backing,
        },
        "fingerprints": d.prints.model_dump(mode="json"),
    }


def always(raw: float) -> TreeModel:
    """A one-leaf model that gives every page the same answer."""
    return TreeModel(
        {"features": NAMES, "trees": [{"f": [-1], "t": [0.0], "l": [-1], "r": [-1], "v": [raw]}]}
    )


def test_the_list_is_clean():
    sites = honest_check.read_list()
    assert len(sites) >= 60 and len(sites) == len(set(sites))
    assert all(s.startswith(("https://", "http://")) and " " not in s for s in sites)


def test_a_saved_page_gives_the_same_numbers_as_the_scan_did():
    url = "https://lemoncakes-example.com/menu"
    scan = scan_of(url, BENIGN, rule_score=16, backing=6)
    row = honest_check.row_from_scan(url, scan)
    assert (row["rule_score"], row["backing"]) == (16, 6)  # as the scan server worked them out
    assert "html" not in json.dumps(row)
    saved = json.loads(json.dumps(row))  # as it comes back from the file
    numbers, link = honest_check.features(saved)
    assert numbers == digest_page(url, BENIGN).features
    assert link.host == "lemoncakes-example.com"


def test_pages_that_were_not_really_seen_are_left_out():
    url = "https://lemoncakes-example.com/"
    assert honest_check.row_from_scan(url, {"analysis": {"page": {"captured": False}}}) is None
    wall = "<title>Just a moment...</title><p>Verifying you are human.</p>"
    assert honest_check.row_from_scan(url, scan_of(url, wall, bot_check="Cloudflare challenge")) is None
    # A real page that only carries a CAPTCHA is kept.
    assert honest_check.row_from_scan(url, scan_of(url, BENIGN, bot_check="reCAPTCHA")) is not None


def test_rating_follows_the_scan_rules(tmp_path):
    small = honest_check.row_from_scan(
        "https://lemoncakes-example.com/", scan_of("https://lemoncakes-example.com/", BENIGN)
    )
    backed = honest_check.row_from_scan(
        "https://lemoncakes-example.com/a",
        scan_of("https://lemoncakes-example.com/a", BENIGN, rule_score=15),
    )
    popular = honest_check.row_from_scan("https://github.com/", scan_of("https://github.com/", BENIGN))
    # Points for free hosting alone: kept in the score, but no backing for the model.
    hosted = honest_check.row_from_scan(
        "https://lemoncakes.github.io/",
        scan_of("https://lemoncakes.github.io/", BENIGN, rule_score=10, backing=0),
    )
    file = tmp_path / "honest-sites.jsonl"
    file.write_text(
        "\n".join(json.dumps(r) for r in (small, backed, popular, hosted)) + "\n", encoding="utf-8"
    )
    rows = honest_check.load(file)
    assert [r["site"] for r in rows] == [small["site"], backed["site"], popular["site"], hosted["site"]]
    assert honest_check.load(tmp_path / "missing.jsonl") == []

    rated = honest_check.rate(rows, always(3.0))  # every page "95% likely scam"
    assert [r["score"] for r in rated] == [MODEL_ALONE_MAX, 15 + 50, 0, 10 + MODEL_ALONE_MAX]
    assert [r["unlimited"] for r in rated] == [50, 15 + 50, 0, 10 + 50]
    assert [r["trusted"] for r in rated] == [False, False, True, False]
    s = honest_check.summary(rated)
    assert (s["pages"], s["at_60"], s["at_95"], s["trusted"]) == (4, 4, 4, 1)
    assert (s["above_safe"], s["unlimited_above_safe"]) == (1, 3)

    calm = honest_check.summary(honest_check.rate(rows, always(-4.0)))
    assert (calm["at_40"], calm["above_safe"]) == (0, 0)


def test_an_older_scan_server_is_refused():
    url = "https://lemoncakes-example.com/"
    old = scan_of(url, BENIGN)
    del old["analysis"]["backing"]
    with pytest.raises(SystemExit):
        honest_check.row_from_scan(url, old)
