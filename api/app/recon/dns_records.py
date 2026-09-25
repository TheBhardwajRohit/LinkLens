"""DNS records for the host and its registered domain. Lookups go to DNS resolvers, never to the site.

Public resolvers (Cloudflare, Google) are asked first: Docker's built-in DNS helper stalls on some
record types. If they're unreachable (some networks block them), the system resolver is used.
"""

import asyncio
import os

import dns.asyncresolver
import dns.exception
import dns.resolver

from app.recon.models import DnsRecords

PUBLIC_RESOLVERS = [
    s.strip() for s in os.environ.get("DNS_RESOLVERS", "1.1.1.1,8.8.8.8").split(",") if s.strip()
]
MAX_TXT = 10
MAX_TXT_LEN = 200
TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT")


def _resolver(servers: list[str] | None) -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver(configure=servers is None)
    if servers:
        resolver.nameservers = servers
    resolver.timeout = 2
    resolver.lifetime = 4
    resolver.use_edns(0, 0, 4096)
    return resolver


async def _query(resolver: dns.asyncresolver.Resolver, name: str, rtype: str) -> list[str] | None:
    """Answers for one record type: [] if there are none, None if the lookup itself failed."""
    try:
        answer = await resolver.resolve(name, rtype)
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.exception.Timeout:
        return None
    return [r.to_text() for r in answer]


async def _all(resolver: dns.asyncresolver.Resolver, host: str, zone: str) -> list[list[str] | None]:
    names = {"A": host, "AAAA": host, "CNAME": host, "MX": zone, "NS": zone, "TXT": zone}
    return list(await asyncio.gather(*(_query(resolver, names[t], t) for t in TYPES)))


async def lookup(host: str, domain: str | None) -> DnsRecords:
    zone = domain or host
    results: list[list[str] | None] = [None] * len(TYPES)
    for servers in (PUBLIC_RESOLVERS or None, None):
        try:
            results = await _all(_resolver(servers), host, zone)
        except dns.resolver.NXDOMAIN:
            return DnsRecords(
                host=host, status="not_found", note="This name doesn't exist in DNS (the site may be gone)."
            )
        if any(r is not None for r in results):
            break  # this resolver works here; no need to try the next

    found = dict(zip(TYPES, results, strict=True))
    failed = [t for t, r in found.items() if r is None]
    if len(failed) == len(TYPES):
        return DnsRecords(host=host, status="timeout", note="DNS didn't answer in time.")

    def get(t: str) -> list[str]:
        return found[t] or []

    return DnsRecords(
        host=host,
        a=sorted(get("A")),
        aaaa=sorted(get("AAAA")),
        cname=[c.rstrip(".") for c in get("CNAME")],
        mx=sorted(m.split()[-1].rstrip(".") for m in get("MX")),
        ns=sorted(n.rstrip(".") for n in get("NS")),
        txt=[t.replace('" "', "").strip('"')[:MAX_TXT_LEN] for t in get("TXT")[:MAX_TXT]],
        note=f"Some lookups didn't answer in time ({', '.join(failed)})." if failed else None,
    )
