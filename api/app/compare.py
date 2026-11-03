"""Compare a finished scan with other tools: VirusTotal and PhishTank, asked about the same link
only when the visitor clicks "Compare". OpenPhish is never asked: its terms forbid showing its data.

The link sent is the pasted link, cleaned of personal data (safety rule 7). A link that leads to a
private address is never sent anywhere. These requests go to the services only, never to the
scanned site (safety rule 1). The answer is saved with the scan, so a shared report shows it too.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app import access, jobs, storage
from app.blacklists import http, virustotal
from app.config import Settings, get_settings
from app.ratelimit import limiter
from app.redact import redact_url

log = logging.getLogger("linklens.compare")
router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]

COMPARES_PER_HOUR = 20
PHISHTANK = "https://checkurl.phishtank.com/checkurl/"
PHISHTANK_AGENT = "phishtank/linklens"  # PhishTank asks for a User-Agent that names the application
VT = "https://www.virustotal.com/api/v3"
# A fresh VirusTotal analysis: wait this long between looks, at most this many looks.
FRESH_WAIT_S = 15
FRESH_LOOKS = 3


def _iso(seconds: int | None) -> str | None:
    return datetime.fromtimestamp(seconds, UTC).isoformat() if seconds else None


def vt_summary(attrs: dict) -> dict:
    """What a VirusTotal report says, in the shape the website shows."""
    results = attrs.get("last_analysis_results") or {}
    flagged = sorted(
        (
            {"engine": name, "category": r.get("category"), "label": r.get("result")}
            for name, r in results.items()
            if r.get("category") in ("malicious", "suspicious")
        ),
        key=lambda f: (f["category"] != "malicious", f["engine"].lower()),
    )
    stats = attrs.get("last_analysis_stats") or {}
    final = attrs.get("last_final_url")
    return {
        "known": True,
        "stats": {
            k: int(stats.get(k, 0)) for k in ("malicious", "suspicious", "harmless", "undetected", "timeout")
        },
        "engines": len(results),
        "flagged": flagged,
        "categories": sorted(set((attrs.get("categories") or {}).values())),
        "reputation": attrs.get("reputation"),
        "votes": attrs.get("total_votes") or {},
        "title": attrs.get("title"),
        "final_url": redact_url(final) if final else None,
        "first_seen": _iso(attrs.get("first_submission_date")),
        "last_analysis": _iso(attrs.get("last_analysis_date")),
    }


async def _vt_call(client, method: str, path: str, key: str, **kwargs):
    """One VirusTotal request inside the shared free limit (4 a minute), or None when it's used up."""
    if not virustotal._allowed():
        return None
    return await client.request(method, VT + path, headers={"x-apikey": key}, **kwargs)


async def ask_virustotal(url: str, key: str, fresh: bool) -> dict:
    if not key:
        return {"status": "not_configured", "note": "No VirusTotal key is set on this scanner."}
    out: dict[str, Any] = {"asked_at": datetime.now(UTC).isoformat(), "fresh": fresh}
    async with http.client(timeout=20) as client:
        if fresh:
            resp = await _vt_call(client, "POST", "/urls", key, data={"url": url})
            if resp is None or resp.status_code == 429:
                return out | {
                    "status": "quota",
                    "note": "The free VirusTotal limit (4 a minute) is used up. Try again in a minute.",
                }
            if resp.status_code == 400:
                message = (resp.json().get("error") or {}).get("message") or "VirusTotal refused the link."
                return out | {"status": "refused", "note": f'VirusTotal refused to analyse it: "{message}".'}
            resp.raise_for_status()
            analysis = (resp.json().get("data") or {}).get("id")
            for _ in range(FRESH_LOOKS):
                await asyncio.sleep(FRESH_WAIT_S)
                look = await _vt_call(client, "GET", f"/analyses/{analysis}", key)
                if look is not None and look.status_code == 200:
                    if ((look.json().get("data") or {}).get("attributes") or {}).get("status") == "completed":
                        break
        resp = await _vt_call(client, "GET", f"/urls/{virustotal.url_id(url)}", key)
        if resp is None or resp.status_code == 429:
            return out | {
                "status": "quota",
                "note": "The free VirusTotal limit (4 a minute) is used up. Try again in a minute.",
            }
        if resp.status_code in (401, 403):
            return out | {"status": "error", "note": "VirusTotal refused this scanner's key."}
        if resp.status_code == 404:
            return out | {"status": "unknown", "note": "VirusTotal has never analysed this link."}
        resp.raise_for_status()
        report = vt_summary((resp.json().get("data") or {}).get("attributes") or {})
    return out | {"status": "found", "report": report}


async def ask_phishtank(url: str) -> dict:
    out: dict[str, Any] = {"asked_at": datetime.now(UTC).isoformat()}
    async with http.client(timeout=15) as client:
        resp = await client.post(
            PHISHTANK, data={"url": url, "format": "json"}, headers={"User-Agent": PHISHTANK_AGENT}
        )
    if resp.status_code == 509:
        return out | {"status": "quota", "note": "PhishTank's lookup limit is used up for now."}
    resp.raise_for_status()
    r = resp.json().get("results") or {}
    if not r.get("in_database"):
        return out | {"status": "not_listed", "note": "No record of this link. Nobody has reported it."}
    verified = bool(r.get("verified")) and bool(r.get("valid"))
    return out | {
        "status": "listed",
        "phish_id": r.get("phish_id"),
        "verified": verified,
        "note": "Confirmed as a phish by its members."
        if verified
        else "Reported, but never verified by its members.",
    }


def leads_to_private(scan: dict) -> bool:
    """True when the pasted link itself pointed at a private or local address (never sent anywhere)."""
    host = (urlsplit(scan.get("url") or "").hostname or "").lower()
    for b in (scan.get("visit") or {}).get("blocked") or []:
        reason = (b.get("reason") or "").lower()
        if b.get("host", "").lower() == host and any(w in reason for w in ("private", "local", "reserved")):
            return True
    return False


async def guarded(coro, name: str) -> dict:
    try:
        return await coro
    except Exception:
        log.warning("%s lookup failed", name, exc_info=True)
        return {"status": "error", "note": f"{name} couldn't be reached."}


async def compare(scan: dict, settings: Settings, fresh: bool) -> dict:
    url = redact_url(scan["url"])
    result: dict[str, Any] = {"url": url, "asked_at": datetime.now(UTC).isoformat()}
    if leads_to_private(scan):
        skipped = {"status": "skipped", "note": "Not sent: the link leads to a private address."}
        return result | {"virustotal": skipped, "phishtank": skipped}
    vt, pt = await asyncio.gather(
        guarded(ask_virustotal(url, settings.virustotal_api_key.get_secret_value(), fresh), "VirusTotal"),
        guarded(ask_phishtank(url), "PhishTank"),
    )
    return result | {"virustotal": vt, "phishtank": pt}


async def save(database_url: str, scan_id: str, comparison: dict) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(
            "UPDATE scans SET result = jsonb_set(result, '{comparison}', %s::jsonb) WHERE id = %s",
            (json.dumps(comparison), scan_id),
        )


class CompareRequest(BaseModel):
    fresh: bool = False  # ask VirusTotal for a new analysis, which adds the link to its public dataset


@router.post("/scans/{scan_id}/compare")
async def compare_scan(scan_id: str, body: CompareRequest, request: Request, settings: SettingsDep) -> dict:
    """Ask VirusTotal and PhishTank about a scanned link and keep their answers with the scan."""
    try:
        scan_id = str(uuid.UUID(scan_id))
    except ValueError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scan with that id.") from err
    who = access.client_address(request, settings)
    if limiter.check(f"compare:{who}", COMPARES_PER_HOUR) is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "That's a lot of comparisons. Try again later."
        )
    job = jobs.get(scan_id)
    try:
        scan = job.result if job and job.result else await storage.load(settings.database_url, scan_id)
    except Exception as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "That scan can't be read right now."
        ) from err
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scan with that id.")
    comparison = await compare(scan, settings, body.fresh)
    if job and job.result:
        job.result["comparison"] = comparison
    try:
        await save(settings.database_url, scan_id, comparison)
    except Exception:
        log.warning("Couldn't save the comparison for %s", scan_id, exc_info=True)
    return comparison
