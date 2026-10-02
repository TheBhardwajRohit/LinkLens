"""Family Finder: does the scanned page look like pages LinkLens already knows?

The scanned page's fingerprints are compared with the page library. Candidates come from one
indexed query (pages sharing a piece of a similarity hash, the exact structure hash, or the site
icon); each candidate is then compared in full with the same rules the nightly grouping uses.
Pages on the scanned site itself don't count: scanning a site twice must not make it look like a
family.
"""

import logging
from datetime import datetime

import psycopg
from pydantic import BaseModel

from app import pages
from app.fingerprint import Fingerprints
from app.redact import redact_url
from app.similarity import Prints, boilerplate, compare, describe, from_hex, unsigned

log = logging.getLogger("linklens.family")

MAX_CANDIDATES = 800
MAX_SHOWN = 12


class SimilarPage(BaseModel):
    page_id: int
    url: str  # personal data removed; shown defanged, never as a link
    site: str | None = None
    label: str = "unknown"  # phish | benign | unknown
    brand: str | None = None
    title: str | None = None
    seen_at: str | None = None
    percent: int = 0
    alike: str = ""  # "nearly the same code and the same page structure"
    has_thumb: bool = False
    family_id: int | None = None


class Family(BaseModel):
    id: int
    label: str  # "fake SBI login page"
    brand: str | None = None
    scam_type: str | None = None
    size: int
    sites: int
    first_seen: str | None = None
    last_seen: str | None = None
    sample_page: int | None = None
    percent: int = 0  # how alike the scanned page is to its closest member


class FamilyResult(BaseModel):
    # matched      the page belongs to a known scam family
    # similar      no family yet, but known scam pages look like it
    # copy         it's a near copy of an ordinary site's page, hosted somewhere else
    # none         nothing in the library looks like it
    # skipped      there was no page to compare (the visit failed)
    # unavailable  the library couldn't be read
    status: str = "none"
    note: str | None = None
    family: Family | None = None
    similar: list[SimilarPage] = []  # closest first
    scam_matches: int = 0
    copied_site: str | None = None
    library_size: int = 0


def prints_of(fp: Fingerprints) -> Prints:
    return Prints(
        fp.tlsh,
        fp.dom_hash,
        from_hex(fp.dom_simhash),
        from_hex(fp.text_simhash),
        from_hex(fp.phash),
        fp.favicon_hash,
        fp.tags,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _candidates(database_url: str, fp: Fingerprints, own_ref: str | None) -> tuple[list, int]:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute(
            """SELECT id, url, site, label, brand, title, seen_at, tlsh, dom_hash, dom_simhash,
                      text_simhash, phash, favicon_hash, tags, family_id, thumb IS NOT NULL
               FROM pages
               WHERE (bands && %s::int[] OR dom_hash = %s OR favicon_hash = %s)
                 AND NOT (source = 'scan' AND source_ref = %s)
               ORDER BY (family_id IS NULL), (label <> 'phish')
               LIMIT %s""",
            (pages.all_bands(fp), fp.dom_hash, fp.favicon_hash, own_ref or "", MAX_CANDIDATES),
        )
        rows = await cur.fetchall()
        cur = await conn.execute("SELECT reltuples::bigint FROM pg_class WHERE relname = 'pages'")
        size = await cur.fetchone()
    return rows, max(int(size[0]) if size else 0, 0)


async def _family(database_url: str, family_id: int) -> Family | None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute(
            """SELECT id, label, brand, scam_type, size, sites, first_seen, last_seen, sample_page
               FROM families WHERE id = %s""",
            (family_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    fid, label, brand, scam_type, size, sites, first, last, sample = row
    return Family(
        id=fid,
        label=label,
        brand=brand,
        scam_type=scam_type,
        size=size,
        sites=sites,
        first_seen=_iso(first),
        last_seen=_iso(last),
        sample_page=sample,
    )


def rank(fp: Fingerprints, rows: list, own_site: str | None) -> list[SimilarPage]:
    """Compare the scanned page with each candidate and keep the real matches, closest first."""
    mine = prints_of(fp)
    found: list[tuple[float, SimilarPage]] = []
    for row in rows:
        (
            pid,
            url,
            site,
            label,
            brand,
            title,
            seen,
            code,
            dom_hash,
            dom,
            text,
            phash,
            icon,
            tags,
            fam,
            thumb,
        ) = row
        if own_site and site == own_site:
            continue
        theirs = Prints(code, dom_hash, unsigned(dom), unsigned(text), unsigned(phash), icon, tags)
        alike = compare(mine, theirs)
        if not alike.match:
            continue
        found.append(
            (
                alike.points,
                SimilarPage(
                    page_id=pid,
                    url=redact_url(url),
                    site=site,
                    label=label,
                    brand=brand,
                    title=title,
                    seen_at=_iso(seen),
                    percent=alike.percent,
                    alike=describe(alike.kinds),
                    has_thumb=bool(thumb),
                    family_id=fam,
                ),
            )
        )
    found.sort(key=lambda item: (-item[0], -item[1].percent))
    return [page for _, page in found]


async def find(
    database_url: str | None,
    fp: Fingerprints,
    *,
    own_ref: str | None = None,
    own_site: str | None = None,
    title: str | None = None,
) -> FamilyResult:
    if not (fp.tlsh or fp.dom_hash or fp.phash):
        return FamilyResult(status="skipped", note="There was no page to compare.")
    if boilerplate(title, fp.words):
        return FamilyResult(
            status="skipped",
            note="This is a standard notice or a nearly empty page, the kind thousands of unrelated "
            "sites show, so comparing it would say nothing.",
        )
    if not database_url:
        return FamilyResult(status="unavailable", note="The page library isn't connected.")
    try:
        rows, size = await _candidates(database_url, fp, own_ref)
        matches = rank(fp, rows, own_site)
        result = FamilyResult(similar=matches[:MAX_SHOWN], library_size=size)
        scams = [m for m in matches if m.label == "phish"]
        result.scam_matches = len(scams)

        in_family = [m for m in matches if m.family_id is not None]
        if in_family:
            # The family most of the close matches belong to.
            counts: dict[int, int] = {}
            for m in in_family:
                counts[m.family_id] = counts.get(m.family_id, 0) + 1
            best = max(counts, key=lambda k: (counts[k], -k))
            family = await _family(database_url, best)
            if family is not None:
                family.percent = max(m.percent for m in in_family if m.family_id == best)
                result.family = family
                result.status = "matched"
                result.note = (
                    f'Looks {family.percent}% like the "{family.label}" family: '
                    f"{family.size:,} pages on {family.sites:,} sites."
                )
                return result
        if scams:
            result.status = "similar"
            n = len(scams)
            result.note = (
                f"Looks {scams[0].percent}% like {n} known scam {'page' if n == 1 else 'pages'}, "
                "not yet grouped into a family."
            )
            return result
        originals = [m for m in matches if m.label == "benign" and "wording" in m.alike and m.percent >= 85]
        if originals:
            result.status = "copy"
            result.copied_site = originals[0].site
            shown = (originals[0].site or "another site").replace(".", "[.]")
            result.note = f"This page is a near copy of a page on {shown}, hosted somewhere else."
            return result
        result.status = "none"
        result.note = (
            f"Nothing among {size:,} known pages looks like this one."
            if size
            else "The page library is empty, so there is nothing to compare with yet."
        )
        return result
    except Exception as err:
        log.warning("family lookup failed: %s", type(err).__name__)
        return FamilyResult(status="unavailable", note="The page library couldn't be read right now.")


async def thumbnail(database_url: str, page_id: int) -> bytes | None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute("SELECT thumb FROM pages WHERE id = %s", (page_id,))
        row = await cur.fetchone()
    return bytes(row[0]) if row and row[0] else None
