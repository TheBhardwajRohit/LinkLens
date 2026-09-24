from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, checks
from app.config import Settings, get_settings

app = FastAPI(title="LinkLens API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

SettingsDep = Annotated[Settings, Depends(get_settings)]


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
