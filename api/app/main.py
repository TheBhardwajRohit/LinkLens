import asyncio
import contextlib
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__, checks, recon, sandbox_client
from app.config import Settings, get_settings
from app.recon.geoip import geo, keep_fresh
from app.recon.models import Recon
from app.urls import UrlError, normalize_url


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Keep the MaxMind location databases fresh in the background (only when keys are set).
    settings = get_settings()
    task = None
    if settings.configured_keys()["maxmind"]:
        task = asyncio.create_task(
            keep_fresh(settings.maxmind_account_id, settings.maxmind_license_key.get_secret_value())
        )
    yield
    if task:
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


class ScanResult(BaseModel):
    id: str
    url: str
    # What the sandbox saw. Captured HTML is removed before it leaves the API:
    # the website only ever shows the screenshot (safety rule 5).
    visit: dict
    recon: Recon


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
        "keys": settings.configured_keys(),
    }


@app.post("/scan")
async def scan(req: ScanRequest, settings: SettingsDep) -> ScanResult:
    """Check the link, have the sandbox visit it, then look up who's behind it. Scoring comes later."""
    try:
        url = normalize_url(req.url)
    except UrlError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err
    try:
        visit = await sandbox_client.visit(settings.sandbox_url, url)
    except sandbox_client.SandboxBusy as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sandbox is busy with another link. Try again in a minute.",
        ) from err
    except sandbox_client.SandboxUnavailable as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sandbox isn't running, so the link can't be opened right now.",
        ) from err
    found = await recon.run_recon(visit, url)
    visit.pop("html", None)
    return ScanResult(id=str(uuid.uuid4()), url=url, visit=visit, recon=found)
