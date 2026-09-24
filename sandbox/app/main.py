"""Sandbox service: the only part of LinkLens allowed to visit target URLs.

Phase 0 is a placeholder with a health route. Phase 2 adds the Playwright
browser, the SSRF guard, redirect tracking, and screenshots.

This service runs on its own network, gets no secrets, and cannot reach
the database.
"""

from fastapi import FastAPI

from app import __version__

app = FastAPI(title="LinkLens Sandbox", version=__version__)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "browser": "not installed yet (phase 2)"}
