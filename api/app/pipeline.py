"""One scan, step by step. Each step reports progress, so the page can tick it off live."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app import recon, sandbox_client, storage
from app.analysis import analyze

log = logging.getLogger("linklens.pipeline")

STEPS = [
    ("sandbox", "Opening the link in the sandbox"),
    ("recon", "Looking up who's behind it"),
    ("analysis", "Reading the page and scoring it"),
    ("save", "Saving the result"),
]

Progress = Callable[[str, str, dict | None], Awaitable[None]]


async def _quiet(step: str, status: str, data: dict | None) -> None:
    pass


def _visit_preview(visit: dict) -> dict:
    """The parts of the visit the graph needs, without the screenshot or HTML."""
    keys = ("requested_url", "final_url", "hops", "contacted_domains", "blocked", "stopped", "duration_ms")
    return {k: visit.get(k) for k in keys}


async def run_scan(
    url: str,
    *,
    sandbox_url: str,
    database_url: str | None,
    scan_id: str | None = None,
    progress: Progress = _quiet,
) -> dict[str, Any]:
    scan_id = scan_id or str(uuid.uuid4())

    await progress("sandbox", "running", None)
    visit = await sandbox_client.visit(sandbox_url, url)
    await progress("sandbox", "done", _visit_preview(visit))

    await progress("recon", "running", None)
    found = await recon.run_recon(visit, url)
    await progress(
        "recon",
        "done",
        {
            "server": found.server.model_dump() if found.server else None,
            "registration": found.registration.model_dump() if found.registration else None,
        },
    )

    await progress("analysis", "running", None)
    verdict = analyze(visit, found.model_dump(), url)
    await progress("analysis", "done", {"score": verdict.score, "verdict": verdict.verdict})

    visit.pop("html", None)  # never leaves the API (safety rule 5)
    result = {
        "id": scan_id,
        "url": url,
        "created_at": datetime.now(UTC).isoformat(),
        "visit": visit,
        "recon": found.model_dump(),
        "analysis": verdict.model_dump(),
        "saved": False,
    }

    if database_url:
        await progress("save", "running", None)
        try:
            await storage.save(database_url, result)
            result["saved"] = True
            await progress("save", "done", None)
        except Exception as err:  # a failed save must not lose the result the user is waiting for
            log.warning("could not save scan: %s", type(err).__name__)
            await progress(
                "save", "failed", {"note": "The result couldn't be saved, so its link won't work later."}
            )
    return result
