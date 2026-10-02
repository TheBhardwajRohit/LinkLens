"""The extras from phase 10: reporting a mistake, trends, and scanning several links at once."""

import asyncio
import logging
import uuid
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app import access, cache, jobs, pipeline, storage
from app.analysis.scamtype import LABELS
from app.config import Settings, get_settings
from app.ratelimit import limiter
from app.redact import EMAIL, MARK
from app.urls import UrlError, normalize_url

log = logging.getLogger("linklens.extras")
router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]

MAX_BULK = 10
FEEDBACK_PER_HOUR = 10
TRENDS_DAYS = 30


# ---------- report a mistake ----------


class Feedback(BaseModel):
    kind: Literal["false_alarm", "missed_scam", "other"]
    note: str = Field(default="", max_length=500)


@router.post("/scans/{scan_id}/feedback", status_code=status.HTTP_201_CREATED)
async def report_mistake(scan_id: str, body: Feedback, request: Request, settings: SettingsDep) -> dict:
    """Tell LinkLens a verdict was wrong. Stored with the scan's id for later review; nothing changes
    automatically. Email addresses in the note are removed before it is stored."""
    try:
        scan_id = str(uuid.UUID(scan_id))
    except ValueError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scan with that id.") from err
    who = access.client_address(request, settings)
    if limiter.check(f"feedback:{who}", FEEDBACK_PER_HOUR) is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "That's a lot of reports. Try again later.")
    job = jobs.get(scan_id)
    try:
        scan = job.result if job and job.result else await storage.load(settings.database_url, scan_id)
    except Exception as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Reports can't be saved right now.") from err
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scan with that id.")
    note = EMAIL.sub(MARK, body.note.strip())[:500] or None
    try:
        await save_feedback(settings.database_url, scan_id, body.kind, note, scan["analysis"])
    except Exception as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Reports can't be saved right now.") from err
    return {"saved": True}


async def save_feedback(database_url: str, scan_id: str, kind: str, note: str | None, analysis: dict) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(
            "INSERT INTO feedback (scan_id, kind, note, verdict, score) VALUES (%s, %s, %s, %s, %s)",
            (scan_id, kind, note, analysis.get("verdict"), analysis.get("score")),
        )


# ---------- how a scan is doing (for lists that follow several scans) ----------


@router.get("/scans/{scan_id}/status")
async def scan_status(scan_id: str, settings: SettingsDep) -> dict:
    """A small answer for pages that follow many scans at once: running, done (with the verdict),
    failed, or unknown. Unlike GET /scans/{id}, it never answers 404 for a scan that's still running."""
    try:
        scan_id = str(uuid.UUID(scan_id))
    except ValueError:
        return {"state": "unknown"}
    job = jobs.get(scan_id)
    if job is not None and job.result is None:
        return {"state": "failed" if job.finished else "running"}
    try:
        scan = job.result if job else await storage.load(settings.database_url, scan_id)
    except Exception:
        return {"state": "unknown"}
    if scan is None:
        return {"state": "unknown"}
    analysis = scan["analysis"]
    return {"state": "done", "verdict": analysis["verdict"], "score": analysis["score"]}


# ---------- trends ----------


async def read_trends(database_url: str) -> dict:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute(
            """SELECT created_at::date AS day, verdict, count(*) FROM scans
               WHERE created_at > now() - make_interval(days => %s) GROUP BY 1, 2 ORDER BY 1""",
            (TRENDS_DAYS,),
        )
        days: dict[str, dict[str, int]] = {}
        for day, verdict, n in await cur.fetchall():
            days.setdefault(day.isoformat(), {"safe": 0, "suspicious": 0, "dangerous": 0})[verdict] = n
        cur = await conn.execute(
            """SELECT scam_type, count(*) FROM scans
               WHERE scam_type IS NOT NULL AND created_at > now() - make_interval(days => %s)
               GROUP BY 1 ORDER BY 2 DESC LIMIT 9""",
            (TRENDS_DAYS,),
        )
        scam_types = [{"id": t, "label": LABELS.get(t, t), "count": n} for t, n in await cur.fetchall()]
        cur = await conn.execute(
            """SELECT brand, count(*) FROM pages WHERE label = 'phish' AND brand IS NOT NULL
               GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""
        )
        brands = [{"brand": b, "pages": n} for b, n in await cur.fetchall()]
        cur = await conn.execute(
            """SELECT id, label, size, sites, last_seen FROM families ORDER BY size DESC LIMIT 8"""
        )
        families = [
            {
                "id": fid,
                "label": label,
                "size": size,
                "sites": sites,
                "last_seen": last.isoformat() if last else None,
            }
            for fid, label, size, sites, last in await cur.fetchall()
        ]
        cur = await conn.execute("SELECT kind, count(*) FROM feedback GROUP BY 1")
        feedback = dict(await cur.fetchall())
    return {
        "days": [{"date": d, **counts} for d, counts in days.items()],
        "scam_types": scam_types,
        "brands": brands,
        "families": families,
        "feedback": feedback,
        "window_days": TRENDS_DAYS,
    }


@router.get("/trends")
async def trends(settings: SettingsDep) -> dict:
    """What LinkLens has been seeing: scans per day, scam types, the brands copied most, and the
    biggest scam families."""
    hit = await cache.get("stats", "trends")
    if hit is not None:
        return hit
    try:
        found = await read_trends(settings.database_url)
    except Exception as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Trends can't be read right now.") from err
    cache.remember("stats", "trends", found, 300)
    return found


# ---------- several links at once ----------


class BulkRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=MAX_BULK)


@router.post("/scans/bulk", status_code=status.HTTP_202_ACCEPTED)
async def start_bulk(body: BulkRequest, request: Request, settings: SettingsDep) -> dict:
    """Start up to 10 scans. They run one after another (the sandbox opens one page at a time).
    Each entry comes back with a scan id to follow, or the reason it was refused."""
    cleaned: list[tuple[str, str | None, str | None]] = []  # (as pasted, cleaned link, problem)
    for raw in body.urls:
        try:
            cleaned.append((raw[:200], normalize_url(raw[:4096]), None))
        except UrlError as err:
            cleaned.append((raw[:200], None, str(err)))
    wanted = sum(1 for _, url, _ in cleaned if url)
    allowed = await access.allow_scan(request, settings, wanted) if wanted else 0

    entries = []
    queue: list[tuple[str, str]] = []
    for raw, url, problem in cleaned:
        if url is None:
            entries.append({"url": raw, "id": None, "error": problem})
        elif allowed <= 0:
            entries.append({"url": url, "id": None, "error": "Your hourly scan limit is used up."})
        else:
            allowed -= 1
            scan_id = str(uuid.uuid4())
            jobs.create(scan_id)
            queue.append((scan_id, url))
            entries.append({"url": url, "id": scan_id, "error": None})

    async def run_all() -> None:
        for scan_id, url in queue:
            await pipeline.run_job(scan_id, url, settings)

    if queue:
        task = asyncio.create_task(run_all())
        jobs.get(queue[0][0]).task = task  # keep a reference so the task isn't garbage collected
    return {"scans": entries}
