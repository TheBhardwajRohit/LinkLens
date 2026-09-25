"""Sandbox service: the only part of LinkLens allowed to visit target URLs.

It runs on its own network, gets no secrets, and cannot reach the database.
Every browser connection goes through the filtering proxy and the SSRF guard.
"""

import asyncio
from importlib.metadata import version

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app import __version__
from app.guard import Guard
from app.visit import VisitResult, visit

app = FastAPI(title="LinkLens Sandbox", version=__version__)

_guard = Guard()
# One visit at a time. A browser uses a lot of memory, and the container has limits.
_slot = asyncio.Semaphore(1)
QUEUE_WAIT_S = 60


class VisitRequest(BaseModel):
    url: str = Field(max_length=4096)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "browser": f"chromium (playwright {version('playwright')})",
    }


@app.post("/visit")
async def visit_link(req: VisitRequest) -> VisitResult:
    try:
        await asyncio.wait_for(_slot.acquire(), QUEUE_WAIT_S)
    except TimeoutError as err:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "The sandbox is busy. Try again in a minute."
        ) from err
    try:
        return await visit(req.url, _guard)
    finally:
        _slot.release()
