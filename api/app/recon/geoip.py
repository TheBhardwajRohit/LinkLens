"""Server location and network owner from MaxMind GeoLite2 (City + ASN), read from local files.

The files are downloaded with your MaxMind account and refreshed weekly. MaxMind's terms say old
copies must be replaced within 30 days of a new release; a weekly check keeps us well inside that.
Lookups are local, so there are no per-request limits and nothing is sent to MaxMind per scan.
"""

import asyncio
import logging
import os
import tarfile
import tempfile
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import geoip2.database
import geoip2.errors
import httpx

from app.recon.models import Server

log = logging.getLogger("linklens.geoip")

EDITIONS = ("GeoLite2-City", "GeoLite2-ASN")
DOWNLOAD = "https://download.maxmind.com/geoip/databases/{edition}/download?suffix=tar.gz"
MAX_AGE_S = 7 * 24 * 3600
CHECK_EVERY_S = 24 * 3600
MAX_DOWNLOAD = 200 * 1024 * 1024


class GeoIP:
    def __init__(self, directory: Path):
        self.dir = directory
        self._readers: dict[str, geoip2.database.Reader] = {}
        self.configured = False
        self.last_error: str | None = None

    def path(self, edition: str) -> Path:
        return self.dir / f"{edition}.mmdb"

    def reload(self) -> None:
        for edition in EDITIONS:
            if self.path(edition).exists():
                old = self._readers.get(edition)
                self._readers[edition] = geoip2.database.Reader(str(self.path(edition)))
                if old:
                    old.close()

    def status(self) -> str:
        if all(e in self._readers for e in EDITIONS):
            return "ok"
        return "downloading" if self.configured else "not configured"

    def lookup(self, ip: str) -> Server:
        if not self._readers:
            return Server(ip=ip, status="not_configured", note="Location data isn't set up (no MaxMind key).")
        server = Server(ip=ip)
        city = self._readers.get("GeoLite2-City")
        if city:
            try:
                r = city.city(ip)
                server.country_code = r.country.iso_code
                server.country = r.country.name
                server.city = r.city.name
                server.latitude = r.location.latitude
                server.longitude = r.location.longitude
                server.accuracy_km = r.location.accuracy_radius
            except geoip2.errors.AddressNotFoundError:
                pass
        asn = self._readers.get("GeoLite2-ASN")
        if asn:
            try:
                r = asn.asn(ip)
                server.asn = r.autonomous_system_number
                server.as_org = r.autonomous_system_organization
            except geoip2.errors.AddressNotFoundError:
                pass
        return server

    async def refresh(self, account_id: str, license_key: str) -> None:
        """Download any database that is missing, or older than a week and newer at MaxMind."""
        self.dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(auth=(account_id, license_key), timeout=120) as client:
            for edition in EDITIONS:
                path = self.path(edition)
                if path.exists() and time.time() - path.stat().st_mtime < MAX_AGE_S:
                    continue
                url = DOWNLOAD.format(edition=edition)
                # A HEAD request doesn't count toward MaxMind's daily download limit.
                head = await client.head(url)
                head.raise_for_status()
                remote = head.headers.get("last-modified")
                if (
                    path.exists()
                    and remote
                    and parsedate_to_datetime(remote).timestamp() <= path.stat().st_mtime
                ):
                    path.touch()
                    continue
                await self._download(client, url, edition, path)
                log.info("downloaded %s", edition)
        self.reload()

    async def _download(self, client: httpx.AsyncClient, url: str, edition: str, path: Path) -> None:
        with tempfile.TemporaryDirectory(dir=self.dir) as tmp:
            archive = Path(tmp) / "db.tar.gz"
            size = 0
            async with client.stream("GET", url, follow_redirects=True) as resp:
                resp.raise_for_status()
                with archive.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_DOWNLOAD:
                            raise ValueError("download too large")
                        f.write(chunk)
            # Read just the .mmdb file out of the archive, without extracting any paths.
            with tarfile.open(archive, "r:gz") as tar:
                member = next(
                    m for m in tar.getmembers() if m.isfile() and m.name.endswith(f"{edition}.mmdb")
                )
                source = tar.extractfile(member)
                staged = Path(tmp) / f"{edition}.mmdb"
                with staged.open("wb") as out:
                    while chunk := source.read(1 << 20):
                        out.write(chunk)
            os.replace(staged, path)


geo = GeoIP(Path(os.environ.get("GEOIP_DIR", "/data/geoip")))


async def keep_fresh(account_id: str, license_key: str) -> None:
    """Background task: load what's on disk, then check for new databases once a day."""
    geo.configured = True
    geo.reload()
    while True:
        try:
            await geo.refresh(account_id, license_key)
            geo.last_error = None
        except Exception as err:  # keep serving the old copy if an update fails
            geo.last_error = type(err).__name__
            log.warning("GeoLite2 update failed: %s", type(err).__name__)
        await asyncio.sleep(CHECK_EVERY_S)
