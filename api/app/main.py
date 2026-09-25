import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import __version__, checks, jobs, pipeline, sandbox_client, storage
from app.analysis.toplist import keep_fresh as keep_toplist_fresh
from app.analysis.toplist import toplist
from app.config import Settings, get_settings
from app.ratelimit import limiter
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
                break
            except Exception as err:
                log.warning("database not ready (%s), retrying", type(err).__name__)
                await asyncio.sleep(2 * (attempt + 1))
        tasks.append(asyncio.create_task(keep_toplist_fresh()))
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
    allow_headers=["Content-Type"],
)

SettingsDep = Annotated[Settings, Depends(get_settings)]


class ScanRequest(BaseModel):
    url: str = Field(max_length=4096)


def _start_checks(req: ScanRequest, request: Request, settings: Settings) -> str:
    """Rate limit, then clean up the link. Raises a plain-words HTTP error if either fails."""
    client = request.client.host if request.client else "unknown"
    wait = limiter.check(client, settings.scan_rate_limit_per_hour)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many scans from your network. Try again in {wait} minute{'s' if wait != 1 else ''}.",
        )
    try:
        return normalize_url(req.url)
    except UrlError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err


def _sandbox_error(err: Exception) -> str:
    if isinstance(err, sandbox_client.SandboxBusy):
        return "The sandbox is busy with another link. Try again in a minute."
    if isinstance(err, sandbox_client.SandboxUnavailable):
        return "The sandbox isn't running, so the link can't be opened right now."
    return "Something went wrong during the scan. Please try again."


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
        "keys": settings.configured_keys(),
    }


@app.post("/scan")
async def scan_now(req: ScanRequest, request: Request, settings: SettingsDep) -> dict:
    """Run a whole scan and return the result in one reply (used by CI and scripts)."""
    url = _start_checks(req, request, settings)
    try:
        return await pipeline.run_scan(
            url, sandbox_url=settings.sandbox_url, database_url=settings.database_url
        )
    except (sandbox_client.SandboxBusy, sandbox_client.SandboxUnavailable) as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _sandbox_error(err)) from err


@app.post("/scans", status_code=status.HTTP_202_ACCEPTED)
async def start_scan(req: ScanRequest, request: Request, settings: SettingsDep) -> dict:
    """Start a scan and return its id at once. Follow it at /scans/{id}/events."""
    url = _start_checks(req, request, settings)
    scan_id = str(uuid.uuid4())
    job = jobs.create(scan_id)

    async def progress(step: str, state: str, data: dict | None) -> None:
        await job.push("step", {"step": step, "status": state, "data": data})

    async def run() -> None:
        try:
            result = await pipeline.run_scan(
                url,
                sandbox_url=settings.sandbox_url,
                database_url=settings.database_url,
                scan_id=scan_id,
                progress=progress,
            )
            job.result = result
            await job.push("done", result, final=True)
        except Exception as err:
            if not isinstance(err, (sandbox_client.SandboxBusy, sandbox_client.SandboxUnavailable)):
                log.exception("scan failed")
            await job.push("error", {"message": _sandbox_error(err)}, final=True)

    job.task = asyncio.create_task(run())
    return {"id": scan_id, "url": url, "steps": [{"id": s, "label": label} for s, label in pipeline.STEPS]}


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
