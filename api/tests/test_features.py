"""The feature list the model learns from: fixed order, plain numbers, nothing that leaks the label."""

from pathlib import Path

from app.library import digest_page
from app.ml.features import NAMES, vector

PAGES = Path(__file__).parent / "fixtures" / "pages"


def numbers(name: str, url: str) -> dict[str, float]:
    d = digest_page(url, (PAGES / name).read_text(encoding="utf-8"))
    assert len(d.features) == len(NAMES)
    return dict(zip(NAMES, d.features, strict=True))


def test_names_are_unique_and_leave_out_popularity():
    assert len(NAMES) == len(set(NAMES))
    assert not any("tranco" in n or "official" in n for n in NAMES)


def test_a_fake_bank_page_lights_up_the_right_numbers():
    f = numbers("sbi_kyc.html", "https://sbi-kyc-update.com/login")
    assert f["asks_otp"] == 1 and f["asks_password"] == 1
    assert f["password_fields"] >= 1
    assert f["form_to_other_domain"] == 1
    assert f["lookalike"] == 1 and f["lookalike_combo"] == 1
    assert f["impersonated"] >= 1
    assert f["phrases_urgency"] >= 1
    assert f["https"] == 1 and f["hyphens"] == 2


def test_a_plain_page_stays_quiet():
    f = numbers("benign.html", "https://example.org/about")
    assert f["asks_count"] == 0 and f["lookalike"] == 0 and f["impersonated"] == 0
    assert f["captured"] == 1


def test_every_number_is_finite_even_without_a_page():
    d = digest_page("https://example.org/", None)
    assert d.features[NAMES.index("captured")] == 0
    assert all(x == x and abs(x) < 1e9 for x in d.features)


def test_vector_matches_names_for_new_page_counts():
    html = (
        "<html><head><meta name='robots' content='noindex,nofollow'>"
        "<meta http-equiv='refresh' content='5;url=/x'>"
        "<script src='https://cdn.example.net/a.js'></script><script>var a=1</script></head>"
        "<body><img src='a.png'><img src='b.png'><form><input type='hidden' name='t'>"
        "<input type='password' name='p'></form></body></html>"
    )
    d = digest_page("https://example.org/", html)
    f = dict(zip(NAMES, vector(d.link, d.page, d.prints, 0), strict=True))
    assert (f["scripts"], f["external_scripts"], f["images"]) == (2, 1, 2)
    assert f["meta_refresh"] == 1 and f["noindex"] == 1
    assert f["hidden_fields"] == 1 and f["password_fields"] == 1
