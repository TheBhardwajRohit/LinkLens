"""Phishing.Database: free lists of active phishing links and domains (MIT license), checked locally.

The two lists are downloaded into the lists volume and refreshed every few hours. Only a short
hash of each entry is kept in memory (8 bytes each), so half a million domains cost a few MB.
Nothing is sent anywhere when a link is checked.
Source: https://github.com/Phishing-Database/Phishing.Database
"""

import asyncio
import bisect
import logging
import os
import time
from array import array
from hashlib import blake2b
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import tldextract

from app.analysis.toplist import toplist
from app.blacklists.models import SourceResult
from app.recon.net import USER_AGENT

log = logging.getLogger("linklens.lists")

ID = "phishing_database"
NAME = "Phishing.Database"
HOME = "https://github.com/Phishing-Database/Phishing.Database"
FILES = {
    "links": "https://phish.co.za/latest/phishing-links-ACTIVE.txt",
    "domains": "https://phish.co.za/latest/phishing-domains-ACTIVE.txt",
}
REFRESH_S = 6 * 3600
MAX_BYTES = 80_000_000

# Private suffixes on, so evil.github.io is one site and github.io is never matched as a whole.
_sites = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)


def _hash(text: str) -> int:
    return int.from_bytes(blake2b(text.encode("utf-8", "ignore"), digest_size=8).digest(), "big")


def link_keys(url: str) -> list[str]:
    """The forms of a link to look up: host + path + query, then host + path."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return []
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return []
    path = parts.path.rstrip("/")
    keys = [host + path + ("?" + parts.query if parts.query else ""), host + path]
    return list(dict.fromkeys(keys))


def host_keys(host: str) -> list[str]:
    """The host and each parent, stopping at the site itself (evil.github.io, not github.io)."""
    host = host.lower().rstrip(".")
    # Unknown endings (not on the public suffix list) fall back to the last two labels.
    floor = _sites(host).top_domain_under_public_suffix or ".".join(host.split(".")[-2:])
    keys = [host]
    while keys[-1] != floor and "." in keys[-1]:
        parent = keys[-1].split(".", 1)[1]
        if len(parent) < len(floor):
            break
        keys.append(parent)
    return keys


class KnownLists:
    def __init__(self, directory: Path):
        self.dir = directory
        self.sets: dict[str, array] = {"links": array("Q"), "domains": array("Q")}
        self.updated: float | None = None

    def _path(self, name: str) -> Path:
        return self.dir / f"phishing-database-{name}.txt"

    @property
    def ready(self) -> bool:
        return any(len(a) for a in self.sets.values())

    def status(self) -> dict:
        return {
            "links": len(self.sets["links"]),
            "domains": len(self.sets["domains"]),
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.updated))
            if self.updated
            else None,
        }

    def load(self) -> None:
        for name in FILES:
            path = self._path(name)
            if not path.exists():
                continue
            hashes = []
            with path.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if name == "links":
                        hashes += [_hash(k) for k in link_keys(line)[:1]]
                    else:
                        hashes.append(_hash(line.lower().rstrip(".")))
            hashes.sort()
            self.sets[name] = array("Q", hashes)
            self.updated = max(self.updated or 0, path.stat().st_mtime)

    def _has(self, name: str, key: str) -> bool:
        arr = self.sets[name]
        h = _hash(key)
        i = bisect.bisect_left(arr, h)
        return i < len(arr) and arr[i] == h

    def has_link(self, url: str) -> bool:
        return any(self._has("links", k) for k in link_keys(url))

    def has_domain(self, host: str) -> str | None:
        return next((k for k in host_keys(host) if self._has("domains", k)), None)

    async def refresh(self) -> None:
        """Download each list again if it changed (the server's ETag tells us)."""
        self.dir.mkdir(parents=True, exist_ok=True)
        changed = False
        async with httpx.AsyncClient(
            timeout=120, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            for name, url in FILES.items():
                path, tag = self._path(name), self._path(name).with_suffix(".etag")
                fresh = path.exists() and time.time() - path.stat().st_mtime < REFRESH_S
                if fresh:
                    continue
                headers = {"If-None-Match": tag.read_text().strip()} if path.exists() and tag.exists() else {}
                async with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 304:
                        os.utime(path)
                        continue
                    resp.raise_for_status()
                    tmp = path.with_suffix(".tmp")
                    size = 0
                    with tmp.open("wb") as out:
                        async for chunk in resp.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_BYTES:
                                raise ValueError(f"{name} list is larger than expected")
                            out.write(chunk)
                    if size < 1000:
                        raise ValueError(f"{name} list looks incomplete")
                    os.replace(tmp, path)
                    if resp.headers.get("etag"):
                        tag.write_text(resp.headers["etag"])
                    changed = True
        if changed or not self.ready:
            await asyncio.to_thread(self.load)
            log.info("Phishing.Database loaded: %s", self.status())

    def check(self, urls: list[str]) -> SourceResult:
        result = SourceResult(id=ID, name=NAME, reference=HOME)
        if not self.ready:
            result.status = "skipped"
            result.note = "The phishing lists haven't been downloaded yet."
            return result
        urls = list(dict.fromkeys(urls))
        for url in urls:
            if self.has_link(url):
                result.status = "listed"
                result.matched = [url]
                result.threats = ["phishing"]
                result.detail = {"match": "link"}
                result.note = "This exact link is on the list of active phishing links."
                return result
        for url in urls:
            host = (urlsplit(url).hostname or "").lower()
            match = self.has_domain(host) if host else None
            if match:
                site = _sites(host).top_domain_under_public_suffix
                popular = toplist.rank(site) is not None
                result.status = "listed"
                result.matched = [url]
                result.threats = ["phishing"]
                result.detail = {"match": "domain", "domain": match, "popular": popular}
                result.note = "This site is on the list of active phishing domains." + (
                    " It's a popular site, so the listing may be about one page on it." if popular else ""
                )
                return result
        result.status = "clean"
        n = self.status()
        result.note = f"Not among {n['links']:,} phishing links and {n['domains']:,} phishing domains."
        return result


known = KnownLists(Path(os.environ.get("LISTS_DIR", "/data/lists")))


async def keep_fresh() -> None:
    await asyncio.to_thread(known.load)
    while True:
        try:
            await known.refresh()
        except Exception as err:  # keep using the old copy if a refresh fails
            log.warning("Phishing.Database refresh failed: %s", type(err).__name__)
        await asyncio.sleep(REFRESH_S / 6)
