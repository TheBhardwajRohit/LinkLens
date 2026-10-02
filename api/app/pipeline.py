"""One scan, step by step. Each step reports progress, so the page can tick it off live."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app import blacklists, recon, sandbox_client, storage
from app.analysis import analyze
from app.config import Settings

log = logging.getLogger("linklens.pipeline")

STEPS = [
    ("blacklists", "Checking known scam lists"),
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
    settings: Settings,
    scan_id: str | None = None,
    progress: Progress = _quiet,
) -> dict[str, Any]:
    scan_id = scan_id or str(uuid.uuid4())

    # The quick answer first: is the pasted link already on a known list?
    await progress("blacklists", "running", None)
    listed = await blacklists.check(blacklists.links_to_check(url), settings)
    await progress("blacklists", "done", blacklists.summary(listed))

    await progress("sandbox", "running", None)
    visit = await sandbox_client.visit(settings.sandbox_url, url)
    await progress("sandbox", "done", _visit_preview(visit))

    await progress("recon", "running", None)
    # Now that the real destination is known, check it and the stops on the way as well.
    # Links already checked come from the cache, so this costs nothing extra for them.
    every_link = blacklists.links_to_check(url, visit)
    recheck = every_link != listed.checked
    found, listed = await asyncio.gather(
        recon.run_recon(visit, url),
        blacklists.check(every_link, settings) if recheck else _same(listed),
    )
    await progress(
        "recon",
        "done",
        {
            "server": found.server.model_dump() if found.server else None,
            "registration": found.registration.model_dump() if found.registration else None,
            "listed_by": listed.listed_by,
        },
    )

    await progress("analysis", "running", None)
    verdict = analyze(visit, found.model_dump(), url, listed.model_dump())
    await progress("analysis", "done", {"score": verdict.score, "verdict": verdict.verdict})

    visit.pop("html", None)  # never leaves the API (safety rule 5)
    result = {
        "id": scan_id,
        "url": url,
        "created_at": datetime.now(UTC).isoformat(),
        "visit": visit,
        "recon": found.model_dump(),
        "blacklists": listed.model_dump(),
        "analysis": verdict.model_dump(),
        "saved": False,
    }

    if settings.database_url:
        await progress("save", "running", None)
        try:
            await storage.save(settings.database_url, result)
            result["saved"] = True
            await progress("save", "done", None)
        except Exception as err:  # a failed save must not lose the result the user is waiting for
            log.warning("could not save scan: %s", type(err).__name__)
            await progress(
                "save", "failed", {"note": "The result couldn't be saved, so its link won't work later."}
            )
    return result


async def _same[T](value: T) -> T:
    return value
