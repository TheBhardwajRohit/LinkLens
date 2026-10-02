"""Feed ingestion: take fresh links from free scam feeds, open each one in the sandbox, and keep
its fingerprints, so new scam pages join the page library within about an hour.

Three steps, so the step that touches live scam pages has no secrets (safety rule 2):

    plan    reads the feeds and picks links not seen before        (may read the database)
    visit   opens each link in the sandbox and fingerprints it     (no secrets, no database)
    store   looks up who's behind each page and saves the row      (database, MaxMind key)

Raw HTML and full screenshots never leave the visit step. Only fingerprints, a few facts, and a
small thumbnail are passed on. Never run the visit step on a personal computer or a campus
network (safety rule 10); it is made for GitHub Actions runners or a separate server.

    python -m jobs.ingest plan  --out urls.json --max 20
    python -m jobs.ingest visit --in urls.json --out pages.jsonl --sandbox http://localhost:8100
    python -m jobs.ingest store --in pages.jsonl
"""

import argparse
import asyncio
import base64
import json
import os
import random
import re
from hashlib import blake2b
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app import pages, recon, sandbox_client
from app.fingerprint import Fingerprints, favicon_hash, screenshot_phash, thumbnail
from app.library import digest_page
from app.recon.geoip import geo
from app.recon.net import USER_AGENT
from app.redact import redact_url
from app.urls import UrlError, normalize_url
from jobs.common import connect, now, say

# name -> lists of links. Phishing.Database is MIT licensed. OpenPhish's community feed is
# supported but off unless FEEDS names it, because its terms forbid passing the data on.
FEEDS: dict[str, dict[str, str]] = {
    "phishing_database": {
        "new": "https://phish.co.za/latest/phishing-links-NEW-today.txt",
        "active": "https://phish.co.za/latest/phishing-links-ACTIVE.txt",
    },
    "openphish": {
        "new": "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
    },
}
DEFAULT_FEEDS = "phishing_database"
MAX_LIST_BYTES = 40_000_000
MAX_PER_RUN = 40
# Pages that load but aren't the scam any more: suspended, parked, or blocked.
DEAD_TITLE = re.compile(
    r"suspended|not found|\b40[34]\b|forbidden|access denied|domain (is )?for sale|parked|"
    r"just a moment|attention required|site can.t be reached|default web ?page|coming soon|"
    r"account (has been )?(disabled|terminated)|deceptive site|phishing (warning|detected)",
    re.I,
)
NOT_CAPTURED = ("blocked", "unreachable", "download", "crashed", "error")


def url_hash(url: str) -> bytes:
    return blake2b(url.encode("utf-8", "ignore"), digest_size=8).digest()


def enabled_feeds() -> list[str]:
    names = [n.strip() for n in (os.environ.get("FEEDS") or DEFAULT_FEEDS).split(",") if n.strip()]
    return [n for n in names if n in FEEDS]


def clean_links(text: str) -> list[str]:
    """The usable links in a feed file: http(s), public, not absurdly long."""
    links = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or len(line) > 1500:
            continue
        try:
            links.append(normalize_url(line))
        except UrlError:
            continue
    return list(dict.fromkeys(links))


def _site(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return ".".join(host.split(".")[-2:])


def choose(new: list[str], backlog: list[str], seen: set[bytes], limit: int, rng: random.Random) -> list[str]:
    """Newest links first, then a random handful from the backlog. One link per site per run, so one
    noisy site can't fill the run."""
    picked: list[str] = []
    sites: set[str] = set()
    pool = list(backlog)
    rng.shuffle(pool)
    for url in list(new) + pool:
        if len(picked) >= limit:
            break
        if url_hash(url) in seen or _site(url) in sites:
            continue
        sites.add(_site(url))
        seen.add(url_hash(url))
        picked.append(url)
    return picked


def _download(url: str) -> str:
    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            body = bytearray()
            for chunk in resp.iter_bytes():
                body += chunk
                if len(body) > MAX_LIST_BYTES:
                    raise ValueError("feed is larger than expected")
    return body.decode("utf-8", "ignore")


def plan(args: argparse.Namespace) -> None:
    limit = max(0, min(args.max, MAX_PER_RUN))
    conn = connect()
    if conn is None and not args.dry_run:
        say("No DATABASE_URL, so there is nowhere to store pages. Nothing planned.")
        Path(args.out).write_text("[]", encoding="utf-8")
        return

    jobs_out: list[dict] = []
    rng = random.Random()
    per_feed = max(limit // max(len(enabled_feeds()), 1), 1)
    for name in enabled_feeds():
        lists = FEEDS[name]
        try:
            new = clean_links(_download(lists["new"]))
            backlog = clean_links(_download(lists["active"])) if "active" in lists else []
        except Exception as err:
            say(f"{name}: feed could not be read ({type(err).__name__})")
            continue
        seen: set[bytes] = set()
        if conn is not None:
            hashes = [url_hash(u) for u in new + backlog]
            cur = conn.execute("SELECT url_hash FROM feed_urls WHERE url_hash = ANY(%s)", (hashes,))
            seen = {bytes(r[0]) for r in cur.fetchall()}
        picked = choose(new, backlog, seen, per_feed, rng)
        if conn is not None and picked:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO feed_urls (url_hash, source) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    [(url_hash(u), name) for u in picked],
                )
        say(f"{name}: {len(new):,} new today, {len(backlog):,} active, {len(picked)} picked")
        jobs_out += [{"url": u, "source": name} for u in picked]
    Path(args.out).write_text(json.dumps(jobs_out), encoding="utf-8")
    say(f"Planned {len(jobs_out)} links.")


def looks_dead(record: dict) -> bool:
    """True when the scam page is gone (taken down, suspended, parked) or never loaded."""
    if record.get("stopped") in NOT_CAPTURED or record.get("bot_check"):
        return True
    status = record.get("status")
    if status is not None and status >= 400:
        return True
    prints = record.get("prints") or {}
    if (prints.get("tags") or 0) < 12:
        return True
    return bool(DEAD_TITLE.search(record.get("title") or ""))


def summarize_visit(job: dict, visit: dict) -> dict:
    """Everything worth keeping from one sandbox visit. The HTML, the full screenshot, and the icon
    are read here and then dropped."""
    final_url = visit.get("final_url") or job["url"]
    downloads = bool(visit.get("downloads")) or visit.get("stopped") == "download"
    d = digest_page(final_url, visit.get("html"), downloads)
    prints: Fingerprints = d.prints
    prints.phash = screenshot_phash(visit.get("screenshot_jpeg_b64"))
    prints.favicon_hash = favicon_hash(visit.get("favicon_b64"))
    thumb = thumbnail(visit.get("screenshot_jpeg_b64"))
    record = {
        "source": job["source"],
        "url": redact_url(job["url"]),
        "final_url": redact_url(final_url),
        "title": visit.get("title") or d.page.title,
        "status": visit.get("status"),
        "stopped": visit.get("stopped"),
        "bot_check": visit.get("bot_check"),
        "hops": [
            {"url": redact_url(h["url"]), "blocked": bool(h.get("blocked"))} for h in visit.get("hops") or []
        ],
        "server_ips": visit.get("server_ips") or {},
        "tls": visit.get("tls"),
        "headers": visit.get("headers") or {},
        "prints": prints.model_dump(),
        "site": d.link.site or d.link.registered_domain or d.link.host,
        "brand": d.impersonated[0] if d.impersonated else None,
        "scam_type": d.scam.id if d.scam else None,
        "thumb_b64": base64.b64encode(thumb).decode() if thumb else None,
        "visited_at": now().isoformat(),
    }
    record["alive"] = not looks_dead(record)
    return record


async def _visit_all(jobs_in: list[dict], sandbox_url: str, out: Path) -> None:
    alive = dead = failed = 0
    with out.open("w", encoding="utf-8") as f:
        for i, job in enumerate(jobs_in, 1):
            try:
                visit = await sandbox_client.visit(sandbox_url, job["url"])
            except Exception as err:
                failed += 1
                say(f"  {i}/{len(jobs_in)} sandbox problem ({type(err).__name__})")
                continue
            try:
                record = summarize_visit(job, visit)
            except Exception as err:
                failed += 1
                say(f"  {i}/{len(jobs_in)} could not be read ({type(err).__name__})")
                continue
            f.write(json.dumps(record) + "\n")
            alive += record["alive"]
            dead += not record["alive"]
            say(f"  {i}/{len(jobs_in)} {'page captured' if record['alive'] else 'gone or blocked'}")
    say(f"Visited {len(jobs_in)}: {alive} live pages, {dead} gone, {failed} failed.")


def visit(args: argparse.Namespace) -> None:
    jobs_in = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    asyncio.run(_visit_all(jobs_in, args.sandbox, Path(args.out)))


async def _load_geoip() -> None:
    """Server locations need the MaxMind files. With a key they're downloaded (or refreshed) into
    GEOIP_DIR; without one, pages are stored without a location."""
    account, key = os.environ.get("MAXMIND_ACCOUNT_ID"), os.environ.get("MAXMIND_LICENSE_KEY")
    try:
        if account and key:
            await geo.refresh(account, key)
        else:
            geo.reload()
    except Exception as err:
        say(f"Location data unavailable ({type(err).__name__}); storing pages without it.")


async def _store_all(records: list[dict]) -> list[dict]:
    await _load_geoip()
    rows = []
    for record in records:
        if not record.get("alive"):
            continue
        visit_like = {
            "final_url": record["final_url"],
            "hops": record.get("hops") or [],
            "server_ips": record.get("server_ips") or {},
            "tls": record.get("tls"),
            "headers": record.get("headers") or {},
        }
        try:
            found = (await recon.run_recon(visit_like, record["url"])).model_dump()
        except Exception:
            found = {}
        thumb = base64.b64decode(record["thumb_b64"]) if record.get("thumb_b64") else None
        rows.append(
            pages.page_row(
                source="feed",
                source_ref=url_hash(record["url"]).hex(),
                url=record["final_url"],
                fp=Fingerprints(**record["prints"]),
                site=record.get("site"),
                label="phish",
                brand=record.get("brand"),
                scam_type=record.get("scam_type"),
                title=record.get("title"),
                recon=found,
                thumb=thumb,
            )
        )
    return rows


def store(args: argparse.Namespace) -> None:
    started = now()
    path = Path(args.inp)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    records = [json.loads(line) for line in lines if line.strip()]
    rows = asyncio.run(_store_all(records))
    gone = len(records) - len(rows)
    note = f"{len(rows)} live pages, {gone} gone or blocked"
    conn = connect()
    if conn is None:
        say(f"No DATABASE_URL: dry run. Would store {note}.")
        for row in rows:
            say(f"  {row['site']}  brand={row['brand']}  type={row['scam_type']}  ip={row['ip']}")
        return
    if rows:
        pages.save_many(conn, rows)
    pages.record_run(
        conn, "feeds", started, ok=True, fetched=len(records), added=len(rows), failed=gone, note=note
    )
    # Thumbnails older than 30 days are dropped, to stay inside the free database's 500 MB.
    conn.execute(
        "UPDATE pages SET thumb = NULL WHERE source = 'feed' AND thumb IS NOT NULL "
        "AND added_at < now() - interval '30 days'"
    )
    conn.close()
    say(f"Stored {note}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", required=True)
    p.add_argument("--max", type=int, default=20)
    p.add_argument("--dry-run", action="store_true", help="pick links even without a database")
    p.set_defaults(run=plan)
    v = sub.add_parser("visit")
    v.add_argument("--in", dest="inp", required=True)
    v.add_argument("--out", required=True)
    v.add_argument("--sandbox", default=os.environ.get("SANDBOX_URL", "http://localhost:8100"))
    v.set_defaults(run=visit)
    s = sub.add_parser("store")
    s.add_argument("--in", dest="inp", required=True)
    s.set_defaults(run=store)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
