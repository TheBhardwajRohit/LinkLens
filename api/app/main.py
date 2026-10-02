import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app import (
    __version__,
    access,
    cache,
    checks,
    extras,
    family,
    jobs,
    pages,
    pipeline,
    sandbox_client,
    storage,
)
from app.analysis.toplist import keep_fresh as keep_toplist_fresh
from app.analysis.toplist import toplist
from app.blacklists.lists import keep_fresh as keep_lists_fresh
from app.blacklists.lists import known as known_lists
from app.config import Settings, get_settings
from app.ml import model as page_model
from app.recon.geoip import geo
from app.recon.geoip import keep_fresh as keep_geoip_fresh
from app.redact import redact
from app.urls import UrlError, normalize_url

log = logging.getLogger("linklens")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    tasks: list[asyncio.Task] = []
    if settings.startup_tasks:
        for attempt in range(5):
            try:
                await storage.init(settings.database_url)
                cache.configure(settings.database_url)
                await cache.sweep()
                break
            except Exception as err:
                log.warning("database not ready (%s), retrying", type(err).__name__)
                await asyncio.sleep(2 * (attempt + 1))
        tasks.append(asyncio.create_task(keep_toplist_fresh()))
        if settings.known_lists:
            tasks.append(asyncio.create_task(keep_lists_fresh()))
        if settings.configured_keys()["maxmind"]:
            key = settings.maxmind_license_key.get_secret_value()
            tasks.append(asyncio.create_task(keep_geoip_fresh(settings.maxmind_account_id, key)))
    yield
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="LinkLens API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(extras.router)

SettingsDep = Annotated[Settings, Depends(get_settings)]


class ScanRequest(BaseModel):
    url: str = Field(max_length=4096)


async def _start_checks(req: ScanRequest, request: Request, settings: Settings) -> str:
    """Rate limit (or API key), then clean up the link. Raises a plain-words HTTP error if either fails."""
    await access.allow_scan(request, settings)
    try:
        return normalize_url(req.url)
    except UrlError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err


@app.get("/")
def root() -> dict:
    return {"name": "LinkLens API", "version": __version__, "health": "/health", "docs": "/docs"}


@app.get("/health")
def health(settings: SettingsDep) -> dict:
    results = {
        "database": checks.database(settings.database_url),
        "sandbox": checks.sandbox(settings.sandbox_url),
    }
    return {
        "status": "ok" if all(v == "ok" for v in results.values()) else "degraded",
        "version": __version__,
        "checks": results,
        "geoip": geo.status(),
        "toplist": toplist.list_id or ("loading" if settings.startup_tasks else "off"),
        "phishing_lists": known_lists.status() if settings.known_lists else "off",
        "model": _model_status(),
        "keys": settings.configured_keys(),
    }


def _model_status() -> dict | str:
    loaded = page_model.load()
    return "none" if loaded is None else {"trained": loaded.meta.get("trained"), "trees": len(loaded.trees)}


@app.post("/scan")
async def scan_now(req: ScanRequest, request: Request, settings: SettingsDep) -> dict:
    """Run a whole scan and return the result in one reply (used by CI and scripts)."""
    url = await _start_checks(req, request, settings)
    try:
        return await pipeline.run_scan(url, settings=settings)
    except (sandbox_client.SandboxBusy, sandbox_client.SandboxUnavailable) as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, pipeline.sandbox_error(err)) from err


@app.post("/scans", status_code=status.HTTP_202_ACCEPTED)
async def start_scan(req: ScanRequest, request: Request, settings: SettingsDep) -> dict:
    """Start a scan and return its id at once. Follow it at /scans/{id}/events."""
    url = await _start_checks(req, request, settings)
    scan_id = str(uuid.uuid4())
    job = jobs.create(scan_id)
    job.task = asyncio.create_task(pipeline.run_job(scan_id, url, settings))
    return {"id": scan_id, "url": url, "steps": [{"id": s, "label": label} for s, label in pipeline.STEPS]}


@app.get("/stats")
async def stats(settings: SettingsDep) -> dict:
    """How much LinkLens knows: pages in the library, by source, and when data last came in."""
    hit = await cache.get("stats", "all")
    if hit is not None:
        return hit
    try:
        found = await pages.stats(settings.database_url)
    except Exception as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The data library can't be read right now."
        ) from err
    found["phishing_lists"] = known_lists.status() if settings.known_lists else None
    cache.remember("stats", "all", found, 60)
    return found


@app.get("/pages/{page_id}/thumb")
async def page_thumb(page_id: int, settings: SettingsDep) -> Response:
    """A small picture of a known page, for the sibling list. It is a JPEG that LinkLens made
    itself from its own screenshot, so it can't carry anything from the page."""
    try:
        data = await family.thumbnail(settings.database_url, page_id)
    except Exception as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Pictures can't be read right now.") from err
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture for that page.")
    return Response(
        data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


def _valid_id(scan_id: str) -> str:
    try:
        return str(uuid.UUID(scan_id))
    except ValueError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scan with that id.") from err


@app.get("/scans/{scan_id}/events")
async def scan_events(scan_id: str, settings: SettingsDep) -> StreamingResponse:
    scan_id = _valid_id(scan_id)
    job = jobs.get(scan_id)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if job:
        return StreamingResponse(job.stream(), media_type="text/event-stream", headers=headers)
    saved = await _load(settings, scan_id)

    async def once():
        yield f"event: done\ndata: {json.dumps(saved)}\n\n"

    return StreamingResponse(once(), media_type="text/event-stream", headers=headers)


async def _load(settings: Settings, scan_id: str) -> dict:
    try:
        saved = await storage.load(settings.database_url, scan_id)
    except Exception as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Saved scans can't be read right now."
        ) from err
    if saved is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No scan with that id. It may have expired or never been saved."
        )
    return saved


@app.get("/scans/{scan_id}")
async def get_scan(scan_id: str, settings: SettingsDep) -> dict:
    """A scan by its id, for reopening or sharing. Always the redacted copy: only the person who ran
    the scan sees the link exactly as pasted, in their own live progress stream."""
    scan_id = _valid_id(scan_id)
    job = jobs.get(scan_id)
    if job and job.result:
        return redact(job.result)
    return await _load(settings, scan_id)
