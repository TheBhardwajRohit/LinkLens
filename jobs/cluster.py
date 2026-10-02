"""Nightly family grouping: put pages that come from the same scam kit into one family.

How it works, in plain steps:

1. Read every page's fingerprints from the page library.
2. Find pairs worth comparing: pages that share a piece of a similarity hash, the same exact
   structure hash, or the same site icon. (Comparing every page with every other would take days.)
3. Compare each pair in full. Two pages are linked when at least two different kinds of fingerprint
   agree (see api/app/similarity.py).
4. Linked pages form groups (connected components). A group becomes a scam family when it has at
   least 3 pages on at least 2 different sites and is mostly known scam pages. Groups that are
   mostly ordinary pages are common templates (a blog theme, a parked-domain page) and are skipped.
5. Each family is named after the brand it targets most, and gets a stable number (the id of its
   oldest page), so the number survives from one night to the next.

    python -m jobs.cluster            # group and save
    python -m jobs.cluster --dry-run  # group and only print the result
"""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from app import pages, storage
from app.analysis.brands import display_brand
from app.similarity import MIN_TAGS, Prints, boilerplate, compare, unsigned
from jobs.common import connect, now, say

MIN_PAGES = 3
MIN_SITES = 2
MIN_SCAM_SHARE = 0.6
# A real kit aims at one brand, maybe two. A big group whose pages aim at many different brands is
# usually an artefact (dead links that all bounced to the same search engine, a hosting notice).
MIXED_MIN_BRANDED = 8
MIXED_MAX_PURITY = 0.3
# In a big bucket, each page is compared with a few neighbours and a few fixed "anchor" pages
# instead of with everyone. Near-identical pages still end up linked, without the quadratic cost.
SMALL_BUCKET = 48
NEIGHBOURS = 6
ANCHORS = 10
COMMON_ICON_SITES = 5

NOUNS = {
    "banking": "banking page",
    "credentials": "login page",
    "crypto": "crypto wallet page",
    "prize": "prize page",
    "shop": "shop",
    "tech_support": "support page",
    "malware": "download page",
    "job": "job offer",
    "government": "government notice",
}


@dataclass
class Page:
    id: int
    label: str
    site: str | None
    brand: str | None
    scam_type: str | None
    seen_at: datetime
    prints: Prints
    bands: list[int]
    has_thumb: bool = False
    title: str | None = None
    words: int | None = None


@dataclass
class Family:
    id: int
    label: str
    brand: str | None
    scam_type: str | None
    size: int
    sites: int
    first_seen: datetime
    last_seen: datetime
    sample_page: int
    members: list[int] = field(default_factory=list)
    purity: float = 1.0  # share of its branded scam pages that carry the family's brand


class Groups:
    """Union-find: keeps track of which pages are already linked."""

    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def load(conn) -> list[Page]:
    cur = conn.execute(
        """SELECT id, label, site, brand, scam_type, seen_at, tlsh, dom_hash, dom_simhash, text_simhash,
                  phash, favicon_hash, tags, bands, thumb IS NOT NULL, title, words
           FROM pages ORDER BY id"""
    )
    out = []
    for row in cur:
        pid, label, site, brand, scam, seen, code, dom_hash, dom, text, phash, icon, tags = row[:13]
        bands, thumb, title, words = row[13:]
        prints = Prints(code, dom_hash, unsigned(dom), unsigned(text), unsigned(phash), icon, tags)
        out.append(
            Page(
                id=pid,
                label=label,
                site=site,
                brand=display_brand(brand),
                scam_type=scam,
                seen_at=seen,
                prints=prints,
                bands=list(bands or []),
                has_thumb=bool(thumb),
                title=title,
                words=words,
            )
        )
    return out


def common_icons(library: list[Page]) -> frozenset[int]:
    """Icons that many unrelated ordinary sites use (a hosting panel's default, say) prove nothing."""
    sites: dict[int, set[str]] = defaultdict(set)
    for p in library:
        if p.prints.favicon is not None and p.label == "benign" and p.site:
            sites[p.prints.favicon].add(p.site)
    return frozenset(icon for icon, s in sites.items() if len(s) >= COMMON_ICON_SITES)


def buckets(library: list[Page], icons: frozenset[int]) -> list[list[int]]:
    """Lists of page positions that are worth comparing with each other."""
    found: dict[tuple, list[int]] = defaultdict(list)
    for i, p in enumerate(library):
        # Tiny pages and standard notices (suspended, parked, not found) never join a family.
        if (p.prints.tags or MIN_TAGS) < MIN_TAGS or boilerplate(p.title, p.words):
            continue
        for band in p.bands:
            found[("band", band)].append(i)
        if p.prints.dom_hash:
            found[("dom", p.prints.dom_hash)].append(i)
        if p.prints.favicon is not None and p.prints.favicon not in icons:
            found[("icon", p.prints.favicon)].append(i)
    return [members for members in found.values() if len(members) > 1]


def _pairs(members: list[int], library: list[Page]):
    if len(members) <= SMALL_BUCKET:
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                yield members[x], members[y]
        return
    # Sort so near-identical pages sit next to each other, then compare neighbours and anchors.
    order = sorted(members, key=lambda i: (library[i].prints.dom_hash or "", library[i].prints.text or 0))
    step = max(len(order) // ANCHORS, 1)
    anchors = order[::step][:ANCHORS]
    for pos, i in enumerate(order):
        for j in order[pos + 1 : pos + 1 + NEIGHBOURS]:
            yield i, j
        for a in anchors:
            if a != i:
                yield i, a


def group(library: list[Page]) -> tuple[Groups, int]:
    icons = common_icons(library)
    groups = Groups(len(library))
    compared = 0
    for members in buckets(library, icons):
        for i, j in _pairs(members, library):
            if groups.find(i) == groups.find(j):
                continue  # already known to be together
            compared += 1
            if compare(library[i].prints, library[j].prints, icons).match:
                groups.union(i, j)
    return groups, compared


def name(brand: str | None, scam_type: str | None, title: str | None = None) -> str:
    noun = NOUNS.get(scam_type or "")
    if brand and noun:
        return f"fake {brand} {noun}"
    if brand:
        return f"fake {brand} page"
    if noun:
        return f"{noun} with no clear brand"
    if title:
        return f'pages titled "{title[:40]}"'
    return "unnamed scam kit"


def _top(values: list[str | None], min_share: float) -> str | None:
    counts = Counter(v for v in values if v)
    if not counts:
        return None
    value, n = counts.most_common(1)[0]
    return value if n / len(values) >= min_share else None


def families(library: list[Page], groups: Groups) -> tuple[list[Family], int]:
    """Turn linked groups into scam families. Also returns how many groups were skipped as
    ordinary templates."""
    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(library)):
        members[groups.find(i)].append(i)

    out: list[Family] = []
    templates = 0
    for positions in members.values():
        if len(positions) < MIN_PAGES:
            continue
        group_pages = [library[i] for i in positions]
        sites = {p.site for p in group_pages if p.site}
        scams = [p for p in group_pages if p.label == "phish"]
        ordinary = sum(1 for p in group_pages if p.label == "benign")
        if ordinary >= 2 and len(scams) / (len(scams) + ordinary) < MIN_SCAM_SHARE:
            templates += 1  # mostly ordinary pages: a shared theme, not a scam kit
            continue
        if len(sites) < MIN_SITES or len(scams) < 2:
            continue
        brand = _top([p.brand for p in scams], 0.5)
        scam_type = _top([p.scam_type for p in scams], 0.4)
        branded = [p.brand for p in scams if p.brand]
        purity = Counter(branded).most_common(1)[0][1] / len(branded) if branded else 1.0
        if len(branded) >= MIXED_MIN_BRANDED and purity < MIXED_MAX_PURITY:
            templates += 1  # aimed at many different brands: not one kit
            continue
        title = _top([p.title for p in scams], 0.5)
        oldest = min(group_pages, key=lambda p: p.id)
        with_thumb = [p for p in scams if p.has_thumb]
        sample = max(with_thumb, key=lambda p: p.seen_at) if with_thumb else oldest
        out.append(
            Family(
                id=oldest.id,
                label=name(brand, scam_type, title),
                brand=brand,
                scam_type=scam_type,
                size=len(group_pages),
                sites=len(sites),
                first_seen=min(p.seen_at for p in group_pages),
                last_seen=max(p.seen_at for p in group_pages),
                sample_page=sample.id,
                members=[p.id for p in group_pages],
                purity=round(purity, 2),
            )
        )
    out.sort(key=lambda f: -f.size)
    return out, templates


def save(conn, found: list[Family]) -> None:
    with conn.transaction():
        conn.execute(
            "CREATE TEMP TABLE new_family (page_id BIGINT PRIMARY KEY, family_id BIGINT) ON COMMIT DROP"
        )
        with conn.cursor().copy("COPY new_family (page_id, family_id) FROM STDIN") as copy:
            for fam in found:
                for page_id in fam.members:
                    copy.write_row((page_id, fam.id))
        conn.execute(
            """UPDATE pages p SET family_id = NULL
               WHERE family_id IS NOT NULL
                 AND NOT EXISTS (SELECT 1 FROM new_family n WHERE n.page_id = p.id)"""
        )
        conn.execute(
            """UPDATE pages p SET family_id = n.family_id FROM new_family n
               WHERE p.id = n.page_id AND p.family_id IS DISTINCT FROM n.family_id"""
        )
        conn.execute("DELETE FROM families")
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO families (id, label, brand, scam_type, size, sites, first_seen, last_seen,
                                         sample_page)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        f.id,
                        f.label,
                        f.brand,
                        f.scam_type,
                        f.size,
                        f.sites,
                        f.first_seen,
                        f.last_seen,
                        f.sample_page,
                    )
                    for f in found
                ],
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the families without saving them")
    parser.add_argument("--show", type=int, default=15, help="how many of the biggest families to print")
    args = parser.parse_args()

    started = now()
    conn = connect()
    if conn is None:
        say("No DATABASE_URL, so there are no pages to group.")
        return
    library = load(conn)
    groups, compared = group(library)
    found, templates = families(library, groups)
    in_families = sum(f.size for f in found)
    note = (
        f"{len(found):,} families holding {in_families:,} of {len(library):,} pages; "
        f"{templates:,} common templates skipped; {compared:,} comparisons"
    )
    say(note)
    for fam in found[: args.show]:
        say(f"  #{fam.id}: {fam.label}, {fam.size} pages on {fam.sites} sites, brand purity {fam.purity:.0%}")
    if found:
        weighted = sum(f.purity * f.size for f in found) / in_families
        say(f"Brand purity across all families (weighted by size): {weighted:.0%}")
    if not args.dry_run:
        save(conn, found)
        pages.record_run(conn, "cluster", started, ok=True, fetched=len(library), added=len(found), note=note)
        conn.execute(storage.PRUNE)  # nightly housekeeping: screenshots older than 90 days
        say(f"Saved in {(now() - started).total_seconds():.0f} s.")
    conn.close()


if __name__ == "__main__":
    main()
