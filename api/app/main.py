import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__, checks
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


class ScanAccepted(BaseModel):
    id: str
    status: str
    url: str
    message: str


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


@app.post("/scan", status_code=status.HTTP_202_ACCEPTED)
def scan(req: ScanRequest) -> ScanAccepted:
    """Placeholder. Checks the link and accepts it, but does not scan yet (phase 2)."""
    try:
        url = normalize_url(req.url)
    except UrlError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    return ScanAccepted(
        id=str(uuid.uuid4()),
        status="received",
        url=url,
        message="The real scan arrives in phase 2.",
    )
