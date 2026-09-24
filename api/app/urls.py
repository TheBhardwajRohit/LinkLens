"""Check and clean up a link someone pasted, without ever visiting it.

This only looks at the text of the link. The full SSRF guard (resolve DNS,
block private ranges, re-check every redirect) arrives in phase 2.
"""

import ipaddress
import re
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048

_HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_NON_WEB_SCHEME = re.compile(
    r"^(javascript|data|file|mailto|vbscript|blob|about|ftp|tel|sms|ws|wss|chrome|view-source):",
    re.IGNORECASE,
)
# Common ways people "defang" links so they can't be clicked by accident.
_REFANG = [
    (re.compile(r"^hxxp", re.IGNORECASE), "http"),
    (re.compile(r"\[\.\]|\(\.\)|\{\.\}|\[dot\]", re.IGNORECASE), "."),
    (re.compile(r"\[:\]"), ":"),
]


class UrlError(ValueError):
    """The link can't be scanned. The message is safe to show to the user."""


def refang(text: str) -> str:
    for pattern, replacement in _REFANG:
        text = pattern.sub(replacement, text)
    return text


def normalize_url(raw: str) -> str:
    url = refang(raw.strip())
    if not url:
        raise UrlError("Paste a link first.")
    if len(url) > MAX_URL_LENGTH:
        raise UrlError(f"That link is too long (over {MAX_URL_LENGTH:,} characters).")

    if _HAS_SCHEME.match(url):
        scheme, rest = url.split(":", 1)
        if scheme.lower() not in ("http", "https"):
            raise UrlError("Only http and https links can be scanned.")
        url = scheme.lower() + ":" + rest
    elif _NON_WEB_SCHEME.match(url):
        raise UrlError("Only http and https links can be scanned.")
    else:
        url = "https://" + url

    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError as err:
        raise UrlError("That doesn't look like a valid link.") from err

    if not host or any(c.isspace() for c in host):
        raise UrlError("That doesn't look like a valid link.")
    if host == "localhost" or host.endswith(".localhost"):
        raise UrlError("That's a local address. LinkLens only scans public websites.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise UrlError("That doesn't look like a full web address.") from None
    else:
        if not ip.is_global:
            raise UrlError("That's a private or local address. LinkLens only scans public websites.")

    return url
