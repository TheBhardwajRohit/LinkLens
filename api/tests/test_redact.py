import pytest

from app.redact import redact, redact_url


@pytest.mark.parametrize(
    ("url", "gone"),
    [
        ("https://x.example/login?email=someone@example.com", "someone@example.com"),
        ("https://x.example/reset?token=abc123def456ghi789jkl012mno", "abc123def456"),
        ("https://x.example/a?session=42", "=42"),
        ("https://x.example/a?next=/home&ref=ZXCVBNMASDFGHJKLQWERTYUIOP1234", "ZXCVBNM"),
        ("https://user:hunter2@x.example/", "hunter2"),
        ("https://x.example/u/someone@example.com/profile", "someone@example.com"),
        ("https://x.example/#access_token=abc", "access_token=abc"),
    ],
)
def test_personal_data_is_removed(url, gone):
    out = redact_url(url)
    assert gone not in out
    assert "REDACTED" in out


def test_harmless_links_are_unchanged():
    url = "https://x.example/products/42?page=2&sort=price"
    assert redact_url(url) == url


def test_redact_walks_a_stored_result():
    data = {
        "url": "https://x.example/?email=a@b.co",
        "visit": {
            "hops": [{"url": "https://x.example/?otp=123456"}],
            "downloads": ["https://x.example/f?key=1"],
        },
        "title": "Hello a@b.co",  # only links are redacted
    }
    out = redact(data)
    assert "a@b.co" not in out["url"]
    assert "123456" not in out["visit"]["hops"][0]["url"]
    assert "key=1" not in out["visit"]["downloads"][0]
    assert out["title"] == "Hello a@b.co"
