import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__, checks, sandbox_client
from app.config import Settings, get_settings
from app.urls import UrlError, normalize_url

app = FastAPI(title="LinkLens API", version=__version__)

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
        "keys": settings.configured_keys(),
    }


@app.post("/scan")
async def scan(req: ScanRequest, settings: SettingsDep) -> ScanResult:
    """Check the link, then have the sandbox visit it. Analysis and scoring come in later phases."""
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
    visit.pop("html", None)
    return ScanResult(id=str(uuid.uuid4()), url=url, visit=visit)
