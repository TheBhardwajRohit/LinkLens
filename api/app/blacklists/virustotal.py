"""VirusTotal, public API v3. Lookups only: LinkLens never submits a link for scanning.

Free limit: 4 requests a minute and 500 a day, for non-commercial use. So results are cached for
hours and at most two links are checked per scan.
Docs: https://docs.virustotal.com/reference/url-info
"""

import base64
import time
from collections import deque

from app import cache
from app.blacklists import http
from app.blacklists.models import SourceResult

ID = "virustotal"
NAME = "VirusTotal"
ENDPOINT = "https://www.virustotal.com/api/v3/urls/"
PER_MINUTE = 4
MAX_URLS = 2
FOUND_TTL_S = 6 * 3600
UNKNOWN_TTL_S = 3600
LISTED_AT = 3  # this many vendors calling it malicious counts as listed

_recent: deque[float] = deque(maxlen=PER_MINUTE)


def url_id(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def _allowed() -> bool:
    now = time.monotonic()
    if len(_recent) == PER_MINUTE and now - _recent[0] < 60:
        return False
    _recent.append(now)
    return True


def reset() -> None:
    _recent.clear()


async def _lookup(url: str, key: str) -> dict:
    """{"known": bool, "stats": {...}} for one link, or {"problem": "quota" | "error"}."""
    hit = await cache.get(ID, url)
    if hit is not None:
        return {**hit, "cached": True}
    if not _allowed():
        return {"problem": "quota"}
    async with http.client() as client:
        resp = await client.get(ENDPOINT + url_id(url), headers={"x-apikey": key})
    if resp.status_code == 404:
        value = {"known": False}
        await cache.put(ID, url, value, UNKNOWN_TTL_S)
        return value
    if resp.status_code == 429:
        return {"problem": "quota"}
    if resp.status_code in (401, 403):
        return {"problem": "key"}
    resp.raise_for_status()
    attrs = (resp.json().get("data") or {}).get("attributes") or {}
    stats = attrs.get("last_analysis_stats") or {}
    value = {
        "known": True,
        "stats": {k: int(stats.get(k, 0)) for k in ("malicious", "suspicious", "harmless", "undetected")},
        "last_analysis": attrs.get("last_analysis_date"),
    }
    await cache.put(ID, url, value, FOUND_TTL_S)
    return value


async def check(urls: list[str], key: str) -> SourceResult:
    result = SourceResult(id=ID, name=NAME)
    if not key:
        result.status = "not_configured"
        result.note = "No VirusTotal key is set, so this check was skipped."
        return result
    urls = list(dict.fromkeys(urls))[:MAX_URLS]
    if not urls:
        result.status = "skipped"
        return result

    worst: dict | None = None
    worst_url = None
    problems = []
    cached = []
    for url in urls:
        found = await _lookup(url, key)
        if "problem" in found:
            problems.append(found["problem"])
            continue
        cached.append(bool(found.get("cached")))
        if found["known"] and (worst is None or found["stats"]["malicious"] > worst["stats"]["malicious"]):
            worst, worst_url = found, url
    result.cached = bool(cached) and all(cached)

    if worst is None:
        if "key" in problems:
            result.status = "error"
            result.note = "VirusTotal refused the API key."
        elif problems:
            result.status = "quota"
            result.note = "The free VirusTotal limit (4 checks a minute, 500 a day) is used up for now."
        else:
            result.status = "unknown"
            result.note = "VirusTotal has never analysed this link."
        return result

    stats = worst["stats"]
    total = sum(stats.values())
    bad = stats["malicious"]
    result.detail = {"malicious": bad, "suspicious": stats["suspicious"], "vendors": total}
    result.reference = f"https://www.virustotal.com/gui/url/{url_id(worst_url)}"
    if bad >= LISTED_AT:
        result.status = "listed"
        result.matched = [worst_url]
        result.threats = ["malicious"]
        result.note = f"{bad} of {total} security vendors flag this link as malicious."
    elif bad or stats["suspicious"]:
        result.status = "info"
        n = bad + stats["suspicious"]
        result.note = (
            f"{n} of {total} security vendors {'flags' if n == 1 else 'flag'} this link. "
            "One or two flags are often false alarms."
        )
    else:
        result.status = "clean"
        result.note = f"None of {total} security vendors flag this link."
    return result
