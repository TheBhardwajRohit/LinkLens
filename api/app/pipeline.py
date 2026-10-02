"""One scan, step by step. Each step reports progress, so the page can tick it off live."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app import blacklists, family, graph, jobs, pages, recon, sandbox_client, siblings, storage
from app.analysis import analyze
from app.analysis.lexical import analyze_link
from app.config import Settings
from app.fingerprint import Fingerprints, fingerprint_visit, thumbnail

log = logging.getLogger("linklens.pipeline")

STEPS = [
    ("blacklists", "Checking known scam lists"),
    ("sandbox", "Opening the link in the sandbox"),
    ("recon", "Looking up who's behind it"),
    ("family", "Looking for its family, siblings, and links"),
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

    # Fingerprint the page, then look for pages like it and for sites run by the same people.
    await progress("family", "running", None)
    prints = await asyncio.to_thread(fingerprint_visit, visit)
    where = analyze_link(visit.get("final_url") or url)
    own_site = where.site or where.registered_domain
    kin = await family.find(
        settings.database_url, prints, own_ref=scan_id, own_site=own_site, title=visit.get("title")
    )
    others = await siblings.find(
        settings.database_url,
        found.model_dump(),
        kin,
        own_site,
        free_hosting=where.free_hosting is not None,
        urlscan=settings.urlscan_search,
        urlscan_key=settings.urlscan_api_key.get_secret_value(),
    )
    # The link graph: who links to this site, whom it links to, and what that says about it.
    net = await graph.find(settings.database_url, own_site, prints.out_domains)
    await progress(
        "family",
        "done",
        {"status": kin.status, "family": kin.family.label if kin.family else None, "note": kin.note},
    )

    await progress("analysis", "running", None)
    verdict = analyze(
        visit,
        found.model_dump(),
        url,
        listed.model_dump(),
        kin.model_dump(),
        others.model_dump(),
        net.model_dump(),
        prints,
    )
    await progress("analysis", "done", {"score": verdict.score, "verdict": verdict.verdict})

    visit.pop("html", None)  # never leaves the API (safety rule 5)
    visit.pop("favicon_b64", None)  # only its hash is kept
    result = {
        "id": scan_id,
        "url": url,
        "created_at": datetime.now(UTC).isoformat(),
        "visit": visit,
        "recon": found.model_dump(),
        "blacklists": listed.model_dump(),
        "analysis": verdict.model_dump(),
        "fingerprints": prints.model_dump(),
        "family": kin.model_dump(),
        "siblings": others.model_dump(),
        "graph": net.model_dump(),
        "saved": False,
    }

    if settings.database_url:
        await progress("save", "running", None)
        try:
            await storage.save(settings.database_url, result)
            result["saved"] = True
            await _remember_page(settings.database_url, result, prints)
            await progress("save", "done", None)
        except Exception as err:  # a failed save must not lose the result the user is waiting for
            log.warning("could not save scan: %s", type(err).__name__)
            await progress(
                "save", "failed", {"note": "The result couldn't be saved, so its link won't work later."}
            )
    return result


def sandbox_error(err: Exception) -> str:
    if isinstance(err, sandbox_client.SandboxBusy):
        return "The sandbox is busy with another link. Try again in a minute."
    if isinstance(err, sandbox_client.SandboxUnavailable):
        return "The sandbox isn't running, so the link can't be opened right now."
    return "Something went wrong during the scan. Please try again."


async def run_job(scan_id: str, url: str, settings: Settings) -> None:
    """Run one scan as a background job, reporting each step to whoever follows the job."""
    job = jobs.get(scan_id)
    if job is None:
        return

    async def progress(step: str, state: str, data: dict | None) -> None:
        await job.push("step", {"step": step, "status": state, "data": data})

    try:
        result = await run_scan(url, settings=settings, scan_id=scan_id, progress=progress)
        job.result = result
        await job.push("done", result, final=True)
    except Exception as err:
        if not isinstance(err, (sandbox_client.SandboxBusy, sandbox_client.SandboxUnavailable)):
            log.exception("scan failed")
        await job.push("error", {"message": sandbox_error(err)}, final=True)


def _label(analysis: dict) -> str:
    """What this scan teaches the page library. Only clear cases get a label."""
    link = analysis.get("final_link") or analysis.get("link") or {}
    if analysis["verdict"] == "dangerous":
        return "phish"
    if analysis["verdict"] == "safe" and (link.get("tranco_rank") or link.get("official_brand")):
        return "benign"
    return "unknown"


async def _remember_page(database_url: str, result: dict, prints: Fingerprints) -> None:
    """Add the scanned page's fingerprints to the page library, so later scans can match it."""
    if not (prints.tlsh or prints.dom_hash or prints.phash):
        return  # nothing was captured
    analysis, visit = result["analysis"], result["visit"]
    link = analysis.get("final_link") or analysis.get("link") or {}
    scam = analysis.get("scam_type") or {}
    try:
        row = pages.page_row(
            source="scan",
            source_ref=result["id"],
            url=visit.get("final_url") or result["url"],
            fp=prints,
            site=link.get("site") or link.get("registered_domain"),
            label=_label(analysis),
            brand=scam.get("brand") or link.get("official_brand"),
            scam_type=scam.get("id"),
            title=visit.get("title"),
            recon=result["recon"],
            thumb=await asyncio.to_thread(thumbnail, visit.get("screenshot_jpeg_b64")),
        )
        await pages.save(database_url, row)
    except Exception as err:  # the library is a bonus; the scan result is already saved
        log.warning("could not add the page to the library: %s", type(err).__name__)


async def _same[T](value: T) -> T:
    return value
