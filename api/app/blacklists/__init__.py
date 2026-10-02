"""Blacklists: what known lists and services already say about a link.

Every source runs at the same time with its own time limit, and each one always ends with a
plain status (listed, clean, not configured, quota reached, ...). Personal data is removed from
links before any of them leaves this server (safety rule 7). None of these sources is the scanned
site itself.
"""

import asyncio
import time
from collections.abc import Awaitable
from urllib.parse import urlsplit

from app.blacklists import history, safebrowsing, urlhaus, urlscan, virustotal
from app.blacklists.lists import known
from app.blacklists.models import Blacklists, SourceResult
from app.config import Settings
from app.recon.domains import registered_domain
from app.redact import redact_url

MAX_URLS = 8
TIME_LIMIT_S = 7


async def _guard(coro: Awaitable[SourceResult], source_id: str, name: str) -> SourceResult:
    try:
        return await asyncio.wait_for(coro, TIME_LIMIT_S)
    except TimeoutError:
        return SourceResult(
            id=source_id, name=name, status="timeout", note="This source didn't answer in time."
        )
    except Exception:
        return SourceResult(id=source_id, name=name, status="error", note="This source couldn't be reached.")


def links_to_check(requested_url: str, visit: dict | None = None) -> list[str]:
    """The pasted link, the final page, and the stops in between. Blocked (private) stops are left out."""
    urls = [requested_url]
    if visit:
        urls += [h["url"] for h in visit.get("hops") or [] if h.get("url") and not h.get("blocked")]
        if visit.get("final_url"):
            urls.append(visit["final_url"])
    cleaned = [redact_url(u) for u in urls if u.startswith(("http://", "https://"))]
    # First and last matter most, so keep them when there are too many.
    unique = list(dict.fromkeys(cleaned))
    return unique if len(unique) <= MAX_URLS else unique[: MAX_URLS - 1] + unique[-1:]


async def check(urls: list[str], settings: Settings, *, history_domain: str | None = None) -> Blacklists:
    started = time.monotonic()
    ends = list(dict.fromkeys([urls[0], urls[-1]])) if urls else []
    host = (urlsplit(urls[-1]).hostname or "").lower() if urls else None
    domain = history_domain or (registered_domain(host) if host else None)

    async def local() -> SourceResult:
        return known.check(urls)

    tasks = [
        _guard(
            safebrowsing.check(urls, settings.google_safe_browsing_api_key.get_secret_value()),
            safebrowsing.ID,
            safebrowsing.NAME,
        ),
        _guard(local(), "phishing_database", "Phishing.Database"),
        _guard(
            virustotal.check(ends, settings.virustotal_api_key.get_secret_value()),
            virustotal.ID,
            virustotal.NAME,
        ),
        _guard(urlhaus.check(ends, settings.abusech_auth_key.get_secret_value()), urlhaus.ID, urlhaus.NAME),
    ]
    if settings.urlscan_search:
        tasks.append(
            _guard(urlscan.check(host, settings.urlscan_api_key.get_secret_value()), urlscan.ID, urlscan.NAME)
        )
    tasks.append(_guard(history.check(settings.database_url, domain), history.ID, history.NAME))

    sources = list(await asyncio.gather(*tasks))
    return Blacklists(
        sources=sources,
        listed_by=[s.name for s in sources if s.status == "listed"],
        checked=urls,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def summary(found: Blacklists) -> dict:
    """The small version sent with live progress."""
    return {
        "listed_by": found.listed_by,
        "sources": [{"id": s.id, "name": s.name, "status": s.status} for s in found.sources],
    }
