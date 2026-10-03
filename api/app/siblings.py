"""Sibling Hunter: other sites that seem to be run by the same people. Four separate kinds:

- same server   other sites on the same IP address (our library, plus urlscan.io's public history)
- same owner    sites sharing a certificate, a registrant, or a registrar + name servers + date
- same design   pages with matching fingerprints (from Family Finder)
- lookalikes    small variations of the name that really exist in DNS

Only public records are used. Nothing here visits a site (safety rule 1): lookalike names are
only looked up in DNS, never opened.
"""

import asyncio
import logging
from datetime import date, timedelta

import dns.asyncresolver
import dns.exception
import dns.resolver
import psycopg
import tldextract
from pydantic import BaseModel

from app import cache
from app.blacklists import http
from app.blacklists.lists import known
from app.family import FamilyResult
from app.recon.dns_records import PUBLIC_RESOLVERS

log = logging.getLogger("linklens.siblings")

MAX_ITEMS = 25
MAX_LOOKALIKES = 90
LOOKUP_LIMIT = 30  # DNS lookups running at once
# Networks where one address serves thousands of unrelated sites, so "same server" proves little.
SHARED_NETWORKS = {
    13335: "Cloudflare",
    209242: "Cloudflare",
    54113: "Fastly",
    20940: "Akamai",
    16625: "Akamai",
    63949: "Akamai",
    2635: "Automattic (WordPress.com)",
    36459: "GitHub",
    76: "Netlify",
}
OTHER_ENDINGS = [
    "com",
    "net",
    "org",
    "info",
    "online",
    "site",
    "xyz",
    "top",
    "shop",
    "live",
    "in",
    "co",
    "app",
]
SWAPS = {"o": "0", "0": "o", "l": "1", "1": "l", "i": "1", "e": "3", "a": "4", "s": "5", "g": "q", "m": "rn"}

_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


class Sibling(BaseModel):
    name: str  # a site name, shown defanged and never as a link
    why: str  # one plain phrase: "same IP address", "on the same certificate"
    known_scam: bool = False
    source: str = "library"  # library | urlscan | certificate | dns


class Tab(BaseModel):
    # ok  none (looked, found nothing)  skipped (nothing to look up)  unavailable (a source failed)
    status: str = "none"
    note: str | None = None
    items: list[Sibling] = []
    total: int = 0


class Siblings(BaseModel):
    same_server: Tab = Tab()
    same_owner: Tab = Tab()
    same_design: Tab = Tab()
    lookalikes: Tab = Tab()


def _finish(tab: Tab, items: list[Sibling], none_note: str) -> Tab:
    unique: dict[str, Sibling] = {}
    for item in items:
        kept = unique.get(item.name)
        if kept is None or (item.known_scam and not kept.known_scam):
            unique[item.name] = item
    ordered = sorted(unique.values(), key=lambda s: (not s.known_scam, s.name))
    tab.total = len(ordered)
    tab.items = ordered[:MAX_ITEMS]
    if ordered:
        tab.status = "ok"
    elif tab.status != "unavailable":
        tab.status = "none"
        tab.note = tab.note or none_note
    return tab


# ---------- same server ----------


async def _urlscan_neighbours(ip: str, key: str) -> list[str] | None:
    hit = await cache.get("urlscan_ip", ip)
    if hit is not None:
        return hit
    headers = {"API-Key": key} if key else {}
    async with http.client() as client:
        resp = await client.get(
            "https://urlscan.io/api/v1/search/", params={"q": f'page.ip:"{ip}"', "size": 100}, headers=headers
        )
    if resp.status_code != 200:
        return None
    names = []
    for r in resp.json().get("results") or []:
        name = ((r.get("page") or {}).get("apexDomain") or "").lower()
        if name and name not in names:
            names.append(name)
    await cache.put("urlscan_ip", ip, names, 3600)
    return names


async def same_server(
    database_url: str | None,
    recon: dict,
    own_site: str | None,
    *,
    urlscan: bool,
    urlscan_key: str,
    free_hosting: bool = False,
) -> Tab:
    server = recon.get("server") or {}
    ip, asn = server.get("ip"), server.get("asn")
    if not ip or server.get("status") == "skipped":
        return Tab(status="skipped", note="No public server address was found.")
    tab = Tab()
    shared = SHARED_NETWORKS.get(asn or 0) or ("a free hosting service" if free_hosting else None)
    items: list[Sibling] = []
    if database_url:
        try:
            async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
                cur = await conn.execute(
                    """SELECT site, bool_or(label = 'phish') FROM pages
                       WHERE ip = %s AND site IS NOT NULL AND site <> %s GROUP BY site LIMIT 200""",
                    (ip, own_site or ""),
                )
                items += [
                    Sibling(name=site, why="same IP address", known_scam=bool(scam))
                    for site, scam in await cur.fetchall()
                ]
        except Exception as err:
            log.warning("same-server lookup failed: %s", type(err).__name__)
            tab.status = "unavailable"
    if urlscan and not shared:
        try:
            for name in await _urlscan_neighbours(ip, urlscan_key) or []:
                if name != own_site:
                    items.append(
                        Sibling(name=name, why="seen on this IP address by urlscan.io", source="urlscan")
                    )
        except Exception as err:
            log.warning("urlscan neighbours failed: %s", type(err).__name__)
    for item in items:
        item.known_scam = item.known_scam or known.has_domain(item.name) is not None
    tab = _finish(tab, items, "No other known site uses this server's address.")
    if shared:
        tab.note = (
            f"This address belongs to {shared}, which serves thousands of unrelated sites from the same "
            "addresses. Sharing it says little about who runs the site."
        )
    elif tab.total >= 60:
        tab.note = "Many sites share this address, so it is probably shared hosting."
    return tab


# ---------- same owner ----------


def _cert_neighbours(recon: dict, own_domain: str | None) -> list[Sibling]:
    names: dict[str, None] = {}
    history = recon.get("cert_history") or {}
    for d in history.get("other_domains") or []:
        names[d.lower()] = None
    for n in (recon.get("certificate") or {}).get("names") or []:
        d = _extract(n.lstrip("*.").lower()).top_domain_under_public_suffix
        if d:
            names[d] = None
    return [
        Sibling(name=d, why="on the same security certificate", source="certificate")
        for d in names
        if d and d != own_domain
    ]


async def same_owner(
    database_url: str | None, recon: dict, own_site: str | None, free_hosting: bool = False
) -> Tab:
    if free_hosting:
        # Every site on github.io shares GitHub's certificate and GitHub's registration.
        return Tab(
            status="skipped",
            note="This site sits on a free hosting service. The certificate and the domain record "
            "belong to that service, so they say nothing about who made the site.",
        )
    reg = recon.get("registration") or {}
    own_domain = recon.get("registered_domain")
    if not own_domain:
        return Tab(status="skipped", note="The link has no domain name to look up.")
    tab = Tab()
    items = _cert_neighbours(recon, own_domain)
    registrant = (reg.get("registrant") or "").strip()
    hidden = not registrant or any(
        w in registrant.lower() for w in ("redacted", "privacy", "withheld", "protect")
    )
    nameservers = ",".join(sorted(n.lower().rstrip(".") for n in reg.get("nameservers") or []))
    created = (reg.get("created") or "")[:10]
    if database_url:
        try:
            async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
                if not hidden:
                    cur = await conn.execute(
                        """SELECT site, bool_or(label = 'phish') FROM pages
                           WHERE registrant = %s AND site IS NOT NULL AND site <> %s
                           GROUP BY site LIMIT 100""",
                        (registrant, own_site or ""),
                    )
                    items += [
                        Sibling(name=s, why="registered by the same owner", known_scam=bool(scam))
                        for s, scam in await cur.fetchall()
                    ]
                if nameservers and reg.get("registrar") and created:
                    day = date.fromisoformat(created)
                    cur = await conn.execute(
                        """SELECT site, bool_or(label = 'phish') FROM pages
                           WHERE ns_key = %s AND registrar = %s AND domain_created BETWEEN %s AND %s
                             AND site IS NOT NULL AND site <> %s
                           GROUP BY site LIMIT 100""",
                        (
                            nameservers,
                            reg["registrar"],
                            day - timedelta(days=2),
                            day + timedelta(days=2),
                            own_site or "",
                        ),
                    )
                    items += [
                        Sibling(
                            name=s,
                            why="same registrar and name servers, registered within two days",
                            known_scam=bool(scam),
                        )
                        for s, scam in await cur.fetchall()
                    ]
        except Exception as err:
            log.warning("same-owner lookup failed: %s", type(err).__name__)
            tab.status = "unavailable"
    for item in items:
        item.known_scam = item.known_scam or known.has_domain(item.name) is not None
    tab = _finish(tab, items, "No other site shares this one's certificate or registration details.")
    if hidden and tab.status != "unavailable":
        extra = "The owner's name is hidden in the public record, which is normal."
        tab.note = f"{tab.note} {extra}" if tab.note else extra
    return tab


# ---------- same design ----------


def same_design(family: FamilyResult | None, own_site: str | None) -> Tab:
    if family is None or family.status in ("skipped", "unavailable"):
        return Tab(status=family.status if family else "skipped", note=family.note if family else None)
    items = [
        Sibling(
            name=p.site,
            why=f"{p.percent}% alike: {p.alike}" if p.alike else f"{p.percent}% alike",
            known_scam=p.label == "phish",
        )
        for p in family.similar
        if p.site and p.site != own_site
    ]
    return _finish(Tab(), items, "No known page shares this page's design.")


# ---------- lookalike names ----------


def name_variants(domain: str) -> list[str]:
    """Small variations of a domain name, the kind scammers register in batches: another ending,
    a dropped or doubled letter, swapped neighbours, look-alike characters, an added hyphen or
    digit."""
    parts = _extract(domain.lower())
    label, suffix = parts.domain, parts.suffix
    if not label or not suffix:
        return []
    made: dict[str, None] = {}

    def add(new_label: str, new_suffix: str = suffix) -> None:
        if not new_label or new_label.startswith("-") or new_label.endswith("-") or "--" in new_label:
            return
        candidate = f"{new_label}.{new_suffix}"
        if candidate != f"{label}.{suffix}" and len(new_label) <= 63:
            made[candidate] = None

    for ending in OTHER_ENDINGS:
        add(label, ending)
    for i in range(len(label)):
        add(label[:i] + label[i + 1 :])  # a dropped letter
        add(label[:i] + label[i] + label[i:])  # a doubled letter
        if i + 1 < len(label):
            add(label[:i] + label[i + 1] + label[i] + label[i + 2 :])  # swapped neighbours
        if label[i] in SWAPS:
            add(label[:i] + SWAPS[label[i]] + label[i + 1 :])  # a look-alike character
        if 0 < i and label[i] != "-" and label[i - 1] != "-":
            add(label[:i] + "-" + label[i:])  # an added hyphen
    add(label.replace("-", ""))
    add(label + "s")
    for digit in "123":
        add(label + digit)
    if label[-1:].isdigit():
        add(label[:-1] + str((int(label[-1]) + 1) % 10))
    return list(made)[:MAX_LOOKALIKES]


async def _exists(resolver: dns.asyncresolver.Resolver, name: str, limit: asyncio.Semaphore) -> bool:
    async with limit:
        try:
            await resolver.resolve(name, "A")
            return True
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            return False
        except Exception:
            return False


async def lookalikes(own_site: str | None, free_hosting: bool = False) -> Tab:
    if not own_site:
        return Tab(status="skipped", note="The link has no domain name to vary.")
    if free_hosting:
        return Tab(
            status="skipped",
            note="This site sits on a shared hosting platform, so its name isn't a domain of its own.",
        )
    variants = name_variants(own_site)
    if not variants:
        return Tab(status="skipped", note="This name can't be varied.")
    resolver = dns.asyncresolver.Resolver(configure=not PUBLIC_RESOLVERS)
    if PUBLIC_RESOLVERS:
        resolver.nameservers = PUBLIC_RESOLVERS
    resolver.timeout = 1.5
    resolver.lifetime = 3
    limit = asyncio.Semaphore(LOOKUP_LIMIT)
    found = await asyncio.gather(*(_exists(resolver, v, limit) for v in variants))
    items = [
        Sibling(
            name=v,
            why="a similar name that exists",
            known_scam=known.has_domain(v) is not None,
            source="dns",
        )
        for v, exists in zip(variants, found, strict=True)
        if exists
    ]
    tab = _finish(Tab(), items, f"None of {len(variants)} similar names exist.")
    if tab.status == "ok":
        tab.note = (
            f"{tab.total} of {len(variants)} similar names exist. Existing doesn't mean scam: "
            "some belong to honest owners."
        )
    return tab


# ---------- all four ----------


async def find(
    database_url: str | None,
    recon: dict,
    family: FamilyResult | None,
    own_site: str | None,
    *,
    free_hosting: bool = False,
    urlscan: bool = True,
    urlscan_key: str = "",
) -> Siblings:
    async def guarded(coro, name: str) -> Tab:
        try:
            return await asyncio.wait_for(coro, 8)
        except TimeoutError:
            return Tab(status="unavailable", note="This search took too long.")
        except Exception as err:
            log.warning("%s siblings failed: %s", name, type(err).__name__)
            return Tab(status="unavailable", note="This search couldn't be finished.")

    server, owner, names = await asyncio.gather(
        guarded(
            same_server(
                database_url,
                recon,
                own_site,
                urlscan=urlscan,
                urlscan_key=urlscan_key,
                free_hosting=free_hosting,
            ),
            "server",
        ),
        guarded(same_owner(database_url, recon, own_site, free_hosting), "owner"),
        guarded(lookalikes(own_site, free_hosting), "lookalike"),
    )
    return Siblings(
        same_server=server, same_owner=owner, same_design=same_design(family, own_site), lookalikes=names
    )
