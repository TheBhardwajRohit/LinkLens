"""Google Safe Browsing, Lookup API v4 (non-commercial use only).

One request checks up to 500 links. An empty reply means none are listed. Each match comes with
a cacheDuration, which is how long Google says the link must be treated as unsafe.
Docs: https://developers.google.com/safe-browsing/v4/lookup-api
"""

from app import __version__, cache
from app.blacklists import http
from app.blacklists.models import SourceResult

ID = "safe_browsing"
NAME = "Google Safe Browsing"
ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
ADVISORY = "https://developers.google.com/safe-browsing/v4/advisory"
THREATS = {
    "MALWARE": "malware",
    "SOCIAL_ENGINEERING": "phishing",
    "UNWANTED_SOFTWARE": "unwanted software",
    "POTENTIALLY_HARMFUL_APPLICATION": "a harmful app",
}
CLEAN_TTL_S = 15 * 60
MAX_URLS = 500


def _seconds(duration: str | None) -> float:
    try:
        return max(float((duration or "").rstrip("s")), 60.0)
    except ValueError:
        return 300.0


async def check(urls: list[str], key: str) -> SourceResult:
    result = SourceResult(id=ID, name=NAME, reference=ADVISORY)
    if not key:
        result.status = "not_configured"
        result.note = "No Google Safe Browsing key is set, so this check was skipped."
        return result
    urls = list(dict.fromkeys(urls))[:MAX_URLS]
    if not urls:
        result.status = "skipped"
        return result

    found: dict[str, list[str]] = {}
    todo: list[str] = []
    for url in urls:
        hit = await cache.get(ID, url)
        if hit is None:
            todo.append(url)
        else:
            found[url] = hit["threats"]
    result.cached = not todo

    if todo:
        body = {
            "client": {"clientId": "linklens", "clientVersion": __version__},
            "threatInfo": {
                "threatTypes": list(THREATS),
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in todo],
            },
        }
        # The key goes in a header, not the address, so it can never end up in a log line.
        async with http.client() as client:
            resp = await client.post(ENDPOINT, json=body, headers={"x-goog-api-key": key})
        if resp.status_code == 429:
            result.status = "quota"
            result.note = "Today's free Google Safe Browsing limit is used up. Try again later."
            return result
        if resp.status_code in (400, 401, 403):
            result.status = "error"
            result.note = (
                "Google Safe Browsing refused the request. The API key may be wrong or switched off."
            )
            return result
        resp.raise_for_status()
        fresh: dict[str, tuple[list[str], float]] = {u: ([], CLEAN_TTL_S) for u in todo}
        for match in resp.json().get("matches", []):
            url = (match.get("threat") or {}).get("url")
            if url not in fresh:
                continue
            threat = THREATS.get(match.get("threatType", ""), "a threat")
            threats, _ = fresh[url]
            if threat not in threats:
                threats.append(threat)
            fresh[url] = (threats, _seconds(match.get("cacheDuration")))
        for url, (threats, ttl) in fresh.items():
            found[url] = threats
            await cache.put(ID, url, {"threats": threats}, ttl)

    result.matched = [u for u in urls if found.get(u)]
    result.threats = list(dict.fromkeys(t for u in result.matched for t in found[u]))
    if result.matched:
        result.status = "listed"
        result.note = f"Google lists this link as suspected {' and '.join(result.threats)}."
    else:
        result.status = "clean"
        result.note = "Not on Google's lists. That alone doesn't make a link safe."
    return result
