"""Remove personal data from links before they're stored (safety rule 7).

Links often carry emails, login tokens, or session IDs in the query string ("?email=you@x.com",
"?token=..."). The live result shows the link as pasted; the saved copy has those values replaced.
"""

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MARK = "REDACTED"
SENSITIVE_KEYS = re.compile(
    r"token|key|auth|session|sid|pass|pwd|secret|code|otp|sig|email|mail|user|login|account|phone|mobile"
    r"|jwt|ticket|nonce|state|card|pan|aadhaar|ssn",
    re.I,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TOKENISH = re.compile(r"[A-Za-z0-9_\-.=+/]{24,}")
URL_KEYS = {"url", "requested_url", "final_url", "pending_refresh"}
URL_LIST_KEYS = {"popups", "downloads"}


def _looks_like_token(value: str) -> bool:
    return (
        bool(TOKENISH.fullmatch(value))
        and any(c.isdigit() for c in value)
        and any(c.isalpha() for c in value)
    )


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return EMAIL.sub(MARK, url)
    netloc = parts.netloc
    if "@" in netloc:  # user:password@host
        netloc = f"{MARK}@{netloc.rsplit('@', 1)[1]}"
    query = [
        (k, MARK if SENSITIVE_KEYS.search(k) or EMAIL.search(v) or _looks_like_token(v) else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    path = EMAIL.sub(MARK, parts.path)
    fragment = (
        MARK
        if parts.fragment and (EMAIL.search(parts.fragment) or "token" in parts.fragment)
        else parts.fragment
    )
    return urlunsplit((parts.scheme, netloc, path, urlencode(query, safe=MARK), fragment))


def redact(data: Any) -> Any:
    """Walk a stored result and redact every link in it."""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k in URL_KEYS and isinstance(v, str):
                out[k] = redact_url(v)
            elif k in URL_LIST_KEYS and isinstance(v, list):
                out[k] = [redact_url(x) if isinstance(x, str) else x for x in v]
            else:
                out[k] = redact(v)
        return out
    if isinstance(data, list):
        return [redact(x) for x in data]
    return data
