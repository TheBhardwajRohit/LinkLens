"""urlscan.io search: has anyone scanned this site before? Search only, LinkLens never submits a scan.

Works without a key (30 searches a minute per IP address when checked on 2 Oct 2026). Without an
account the search can't filter by verdict, so a keyless result is history, not a verdict. Only the
site's name is sent, never the full link.
Docs: https://urlscan.io/docs/api/ and https://urlscan.io/docs/search/
"""

from datetime import datetime

from app import cache
from app.blacklists import http
from app.blacklists.models import SourceResult

ID = "urlscan"
NAME = "urlscan.io"
ENDPOINT = "https://urlscan.io/api/v1/search/"
TTL_S = 3600


def _day(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return f"{t.day} {t.strftime('%b %Y')}"


async def _search(query: str, key: str) -> tuple[int, dict | None]:
    headers = {"API-Key": key} if key else {}
    async with http.client() as client:
        resp = await client.get(ENDPOINT, params={"q": query, "size": 1}, headers=headers)
    if resp.status_code != 200:
        return resp.status_code, None
    return 200, resp.json()


async def check(host: str | None, key: str) -> SourceResult:
    result = SourceResult(id=ID, name=NAME)
    if not host:
        result.status = "skipped"
        return result
    hit = await cache.get(ID, host)
    if hit is None:
        code, body = await _search(f'page.domain:"{host}"', key)
        if code == 429:
            result.status = "quota"
            result.note = "urlscan.io's free search limit is used up for now."
            return result
        if code in (401, 403):
            result.status = "error"
            result.note = "urlscan.io refused the request."
            return result
        if body is None:
            result.status = "error"
            result.note = "urlscan.io couldn't be reached."
            return result
        results = body.get("results") or []
        hit = {
            "total": int(body.get("total") or 0),
            "latest": ((results[0].get("task") or {}).get("time") if results else None),
            "malicious": None,
        }
        if key and hit["total"]:
            # Verdict search needs an account; without one urlscan answers 403, which we ignore.
            code, flagged = await _search(f'page.domain:"{host}" AND verdicts.malicious:true', key)
            if code == 200 and flagged is not None:
                hit["malicious"] = int(flagged.get("total") or 0)
        await cache.put(ID, host, hit, TTL_S)
    else:
        result.cached = True

    total = hit["total"]
    result.detail = {"scans": total, "latest": hit["latest"], "malicious": hit["malicious"]}
    result.reference = f"https://urlscan.io/search/#page.domain%3A{host}"
    if not total:
        result.status = "unknown"
        result.note = "Nobody has scanned this site on urlscan.io yet."
        return result
    times = "once" if total == 1 else f"{total:,} times" if total < 10_000 else "over 10,000 times"
    latest = _day(hit["latest"])
    seen = f"Scanned {times} on urlscan.io" + (f", most recently on {latest}." if latest else ".")
    if hit["malicious"]:
        result.status = "listed"
        result.threats = ["malicious"]
        result.note = f"{seen} {hit['malicious']:,} of those scans were judged malicious."
    else:
        result.status = "info"
        result.note = seen + (" None were judged malicious." if hit["malicious"] == 0 else "")
    return result
