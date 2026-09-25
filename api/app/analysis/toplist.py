"""The Tranco top-sites list: a research ranking of the most popular domains, hardened against
manipulation. Being high on it is a good sign, since scam domains rarely stay up long enough to
get popular. We keep the top 100,000 on disk and refresh it monthly.

Free-hosting platforms (github.io, blogspot.com, ...) are ranked as a whole, so the check always
uses the individual site on them (evil.github.io), which is never on the list.
"""

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx

from app.recon.net import USER_AGENT

log = logging.getLogger("linklens.tranco")

LATEST = "https://tranco-list.eu/api/lists/date/latest"
TOP_N = 100_000
MAX_AGE_S = 30 * 24 * 3600
CHECK_EVERY_S = 24 * 3600


class TopList:
    def __init__(self, directory: Path):
        self.dir = directory
        self.path = directory / "tranco-top100k.csv"
        self.ranks: dict[str, int] = {}
        self.list_id: str | None = None

    def load(self) -> None:
        if not self.path.exists():
            return
        ranks: dict[str, int] = {}
        list_id = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#list_id="):
                list_id = line.split("=", 1)[1]
                continue
            rank, _, domain = line.partition(",")
            if rank.isdigit() and domain:
                ranks[domain.strip().lower()] = int(rank)
        self.ranks, self.list_id = ranks, list_id

    def rank(self, site: str | None) -> int | None:
        return self.ranks.get(site.lower()) if site else None

    @property
    def ready(self) -> bool:
        return bool(self.ranks)

    async def refresh(self) -> None:
        if self.path.exists() and time.time() - self.path.stat().st_mtime < MAX_AGE_S:
            if not self.ready:
                self.load()
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(
            timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            meta = (await client.get(LATEST)).raise_for_status().json()
            list_id = meta["list_id"]
            body = (
                (await client.get(f"https://tranco-list.eu/download/{list_id}/{TOP_N}"))
                .raise_for_status()
                .text
            )
        lines = [line for line in body.splitlines() if "," in line][:TOP_N]
        if len(lines) < 1000:
            raise ValueError("Tranco list looks incomplete")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(f"#list_id={list_id}\n" + "\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        self.load()
        log.info("Tranco list %s loaded (%d domains)", list_id, len(self.ranks))


toplist = TopList(Path(os.environ.get("LISTS_DIR", "/data/lists")))


async def keep_fresh() -> None:
    toplist.load()
    while True:
        try:
            await toplist.refresh()
        except Exception as err:  # keep using the old copy if a refresh fails
            log.warning("Tranco refresh failed: %s", type(err).__name__)
        await asyncio.sleep(CHECK_EVERY_S)
