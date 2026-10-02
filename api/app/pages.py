"""The page library: one row of fingerprints per page LinkLens knows about, whether it came from a
user's scan, a research dataset, or a scam feed. Raw HTML is never stored, only fingerprints, a
few facts for finding siblings, and a small thumbnail.

Families (phase 7) and the link graph (phase 8) are built from this table.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import psycopg

from app.fingerprint import Fingerprints, to_signed64
from app.redact import redact_url

log = logging.getLogger("linklens.pages")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,                 -- scan | feed | phreshphish | ...
    source_ref TEXT NOT NULL,             -- the scan id, or the dataset's own id for the page
    url TEXT NOT NULL,                    -- personal data removed
    host TEXT,
    site TEXT,                            -- registered domain (evil.github.io stays whole)
    label TEXT NOT NULL DEFAULT 'unknown',  -- phish | benign | unknown
    brand TEXT,
    scam_type TEXT,
    title TEXT,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),   -- when the page was live
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tlsh TEXT,
    dom_hash TEXT,
    dom_simhash BIGINT,
    text_simhash BIGINT,
    phash BIGINT,
    favicon_hash INTEGER,
    bands INTEGER[] NOT NULL DEFAULT '{}',  -- pieces of the similarity hashes, for fast candidate search
    terms TEXT[] NOT NULL DEFAULT '{}',
    out_domains TEXT[] NOT NULL DEFAULT '{}',
    ip INET,
    asn INTEGER,
    as_org TEXT,
    country TEXT,
    registrar TEXT,
    registrant TEXT,
    domain_created DATE,
    ns_key TEXT,                          -- the name servers, sorted and joined
    cert_domains TEXT[] NOT NULL DEFAULT '{}',
    family_id BIGINT,
    thumb BYTEA,
    UNIQUE (source, source_ref)
);
CREATE INDEX IF NOT EXISTS pages_bands_idx ON pages USING GIN (bands);
CREATE INDEX IF NOT EXISTS pages_dom_hash_idx ON pages (dom_hash) WHERE dom_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_favicon_idx ON pages (favicon_hash) WHERE favicon_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_site_idx ON pages (site);
CREATE INDEX IF NOT EXISTS pages_ip_idx ON pages (ip) WHERE ip IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_asn_idx ON pages (asn) WHERE asn IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_ns_idx ON pages (ns_key) WHERE ns_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_family_idx ON pages (family_id) WHERE family_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS pages_added_idx ON pages (added_at DESC);

CREATE TABLE IF NOT EXISTS families (
    id BIGINT PRIMARY KEY,
    label TEXT NOT NULL,                  -- "fake SBI login"
    brand TEXT,
    scam_type TEXT,
    size INTEGER NOT NULL,
    sites INTEGER NOT NULL DEFAULT 0,     -- how many different sites the pages sit on
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    sample_page BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job TEXT NOT NULL,                    -- feeds | phreshphish | cluster
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ok BOOLEAN NOT NULL,
    fetched INTEGER NOT NULL DEFAULT 0,
    added INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    note TEXT
);
CREATE INDEX IF NOT EXISTS ingest_runs_job_idx ON ingest_runs (job, finished_at DESC);

CREATE TABLE IF NOT EXISTS feed_urls (
    url_hash BYTEA PRIMARY KEY,           -- 8-byte hash of the link, so a link is visited only once
    source TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

BAND_BITS = 16
BANDS_PER_HASH = 4
KINDS = {"dom": 0, "text": 1, "phash": 2}


def band_values(kind: str, hex_hash: str | None) -> list[int]:
    """Split a 64-bit hash into four 16-bit pieces. Two hashes that differ in at most three bits
    always share at least one piece, so shared pieces find the candidates worth comparing fully."""
    if not hex_hash:
        return []
    value = int(hex_hash, 16)
    base = KINDS[kind] * BANDS_PER_HASH
    return [
        (base + i) * (1 << BAND_BITS) + ((value >> (BAND_BITS * i)) & 0xFFFF) for i in range(BANDS_PER_HASH)
    ]


def all_bands(fp: Fingerprints) -> list[int]:
    return (
        band_values("dom", fp.dom_simhash)
        + band_values("text", fp.text_simhash)
        + band_values("phash", fp.phash)
    )


def page_row(
    *,
    source: str,
    source_ref: str,
    url: str,
    fp: Fingerprints,
    site: str | None = None,
    label: str = "unknown",
    brand: str | None = None,
    scam_type: str | None = None,
    title: str | None = None,
    seen_at: datetime | None = None,
    recon: dict | None = None,
    thumb: bytes | None = None,
) -> dict[str, Any]:
    """One row for the `pages` table, as a dict whose keys are the column names."""
    recon = recon or {}
    server = recon.get("server") or {}
    reg = recon.get("registration") or {}
    history = recon.get("cert_history") or {}
    cert = recon.get("certificate") or {}
    nameservers = sorted(n.lower().rstrip(".") for n in reg.get("nameservers") or [])
    cert_domains = list(dict.fromkeys((history.get("other_domains") or []) + (cert.get("names") or [])))[:40]
    clean = redact_url(url)
    return {
        "source": source,
        "source_ref": source_ref,
        "url": clean[:2000],
        "host": (urlsplit(clean).hostname or "").lower() or None,
        "site": site,
        "label": label,
        "brand": brand,
        "scam_type": scam_type,
        "title": (title or "")[:200] or None,
        "seen_at": seen_at or datetime.now(UTC),
        "tlsh": fp.tlsh,
        "dom_hash": fp.dom_hash,
        "dom_simhash": to_signed64(fp.dom_simhash),
        "text_simhash": to_signed64(fp.text_simhash),
        "phash": to_signed64(fp.phash),
        "favicon_hash": fp.favicon_hash,
        "bands": all_bands(fp),
        "terms": fp.terms,
        "out_domains": fp.out_domains,
        "ip": server.get("ip") if server.get("status") == "ok" else None,
        "asn": server.get("asn"),
        "as_org": server.get("as_org"),
        "country": server.get("country_code"),
        "registrar": reg.get("registrar"),
        "registrant": reg.get("registrant"),
        "domain_created": (reg.get("created") or "")[:10] or None,
        "ns_key": ",".join(nameservers) or None,
        "cert_domains": cert_domains,
        "thumb": thumb,
    }


COLUMNS = list(page_row(source="", source_ref="", url="https://example.com/", fp=Fingerprints()))
UPSERT = (
    f"INSERT INTO pages ({', '.join(COLUMNS)}) VALUES ({', '.join('%(' + c + ')s' for c in COLUMNS)}) "
    "ON CONFLICT (source, source_ref) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS if c not in ("source", "source_ref"))
)


async def init(database_url: str) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(SCHEMA)


async def save(database_url: str, row: dict[str, Any]) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(UPSERT, row)


def save_many(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> None:
    """Bulk version for jobs (plain, not async)."""
    with conn.cursor() as cur:
        cur.executemany(UPSERT, rows)


async def stats(database_url: str) -> dict[str, Any]:
    """Numbers for the data health view."""
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute(
            "SELECT source, label, count(*) FROM pages GROUP BY source, label ORDER BY source, label"
        )
        by_source: dict[str, dict[str, int]] = {}
        for source, label, n in await cur.fetchall():
            by_source.setdefault(source, {})[label] = n
        cur = await conn.execute("SELECT count(*), max(added_at) FROM pages")
        total, newest = await cur.fetchone()
        cur = await conn.execute("SELECT count(*), coalesce(sum(size), 0) FROM families")
        families, in_families = await cur.fetchone()
        cur = await conn.execute("SELECT count(*) FROM scans")
        (scans,) = await cur.fetchone()
        cur = await conn.execute(
            """SELECT DISTINCT ON (job) job, started_at, finished_at, ok, fetched, added, failed, note
               FROM ingest_runs ORDER BY job, finished_at DESC"""
        )
        runs = [
            {
                "job": job,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "ok": ok,
                "fetched": fetched,
                "added": added,
                "failed": failed,
                "note": note,
            }
            for job, started, finished, ok, fetched, added, failed, note in await cur.fetchall()
        ]
    return {
        "pages": total,
        "newest_page": newest.isoformat() if newest else None,
        "by_source": by_source,
        "families": families,
        "pages_in_families": int(in_families),
        "scans": scans,
        "last_runs": runs,
    }


def record_run(
    conn: psycopg.Connection,
    job: str,
    started: datetime,
    *,
    ok: bool,
    fetched: int = 0,
    added: int = 0,
    failed: int = 0,
    note: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO ingest_runs (job, started_at, ok, fetched, added, failed, note)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (job, started, ok, fetched, added, failed, note),
    )
