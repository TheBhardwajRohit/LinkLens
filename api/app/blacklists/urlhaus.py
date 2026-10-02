"""URLhaus (abuse.ch): links that hand out malware. Needs a free Auth-Key from auth.abuse.ch.

The link is checked first; if URLhaus doesn't know it, the host is checked.
Docs: https://urlhaus-api.abuse.ch/
"""

from urllib.parse import urlsplit

from app import cache
from app.blacklists import http
from app.blacklists.models import SourceResult

ID = "urlhaus"
NAME = "URLhaus (abuse.ch)"
URL_ENDPOINT = "https://urlhaus-api.abuse.ch/v1/url/"
HOST_ENDPOINT = "https://urlhaus-api.abuse.ch/v1/host/"
MAX_URLS = 2
TTL_S = 3600


class _Problem(Exception):
    pass


async def _post(endpoint: str, field: str, value: str, key: str) -> dict:
    hit = await cache.get(ID, f"{field}:{value}")
    if hit is not None:
        return {**hit, "cached": True}
    async with http.client() as client:
        resp = await client.post(endpoint, data={field: value}, headers={"Auth-Key": key})
    if resp.status_code in (401, 403):
        raise _Problem("key")
    if resp.status_code == 429:
        raise _Problem("quota")
    resp.raise_for_status()
    body = resp.json()
    await cache.put(ID, f"{field}:{value}", body, TTL_S)
    return body


async def check(urls: list[str], key: str) -> SourceResult:
    result = SourceResult(id=ID, name=NAME)
    if not key:
        result.status = "not_configured"
        result.note = "No abuse.ch key is set, so this check was skipped."
        return result
    urls = list(dict.fromkeys(urls))[:MAX_URLS]
    if not urls:
        result.status = "skipped"
        return result

    cached: list[bool] = []
    try:
        for url in urls:
            found = await _post(URL_ENDPOINT, "url", url, key)
            cached.append(bool(found.get("cached")))
            if found.get("query_status") == "ok":
                online = found.get("url_status") == "online"
                result.status = "listed"
                result.matched = [url]
                result.threats = ["malware"]
                result.detail = {"url_status": found.get("url_status"), "tags": (found.get("tags") or [])[:5]}
                result.reference = found.get("urlhaus_reference")
                result.note = "URLhaus lists this link as a malware download" + (
                    " that is live right now." if online else ". It was offline when last checked."
                )
                result.cached = all(cached)
                return result
        hosts = list(dict.fromkeys(h for h in ((urlsplit(u).hostname or "").lower() for u in urls) if h))
        for host in hosts:
            found = await _post(HOST_ENDPOINT, "host", host, key)
            cached.append(bool(found.get("cached")))
            count = int(found.get("url_count") or 0) if found.get("query_status") == "ok" else 0
            if count:
                online = sum(1 for u in found.get("urls") or [] if u.get("url_status") == "online")
                result.status = "listed" if online else "info"
                result.threats = ["malware"] if online else []
                result.detail = {"links_on_host": count, "online": online}
                result.reference = found.get("urlhaus_reference")
                result.note = (
                    f"URLhaus knows {count} malware {'link' if count == 1 else 'links'} on this host"
                    + (f", {online} still live." if online else ", none live right now.")
                )
                result.cached = all(cached)
                return result
    except _Problem as err:
        if str(err) == "key":
            result.status = "error"
            result.note = "URLhaus refused the abuse.ch key."
        else:
            result.status = "quota"
            result.note = "URLhaus asked us to slow down. Try again later."
        return result

    result.cached = bool(cached) and all(cached)
    result.status = "clean"
    result.note = "Not in URLhaus's list of malware links."
    return result
