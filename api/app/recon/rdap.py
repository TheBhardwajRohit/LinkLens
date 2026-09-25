"""RDAP: the modern, JSON version of WHOIS. IANA publishes which server answers for each
top-level domain and each IP range; we look that up, then ask that server."""

import ipaddress
from typing import Any

from app.recon.domains import age_days, parse_date
from app.recon.models import Registration, Server
from app.recon.net import NotFound, TTLCache, get_json

BOOTSTRAP = {
    "dns": "https://data.iana.org/rdap/dns.json",
    "ipv4": "https://data.iana.org/rdap/ipv4.json",
    "ipv6": "https://data.iana.org/rdap/ipv6.json",
}
RDAP_JSON = "application/rdap+json, application/json"

_bootstrap_cache = TTLCache(24 * 3600)
_domain_cache = TTLCache(6 * 3600)
_ip_cache = TTLCache(24 * 3600)


async def _services(kind: str) -> list[tuple[list[str], str]]:
    cached = _bootstrap_cache.get(kind)
    if cached is not None:
        return cached
    data = await get_json(BOOTSTRAP[kind], timeout=10)
    services = []
    for keys, urls in data.get("services", []):
        https = [u for u in urls if u.startswith("https://")]
        if https:
            services.append(([k.lower() for k in keys], https[0].rstrip("/") + "/"))
    _bootstrap_cache.set(kind, services)
    return services


async def domain_server(domain: str) -> str | None:
    tld = domain.rsplit(".", 1)[-1].lower()
    for keys, base in await _services("dns"):
        if tld in keys:
            return base
    return None


async def ip_server(ip: str) -> str | None:
    addr = ipaddress.ip_address(ip)
    best: tuple[int, str] | None = None
    for keys, base in await _services("ipv4" if addr.version == 4 else "ipv6"):
        for cidr in keys:
            net = ipaddress.ip_network(cidr, strict=False)
            if addr in net and (best is None or net.prefixlen > best[0]):
                best = (net.prefixlen, base)
    return best[1] if best else None


def _vcard(entity: dict, field: str) -> str | None:
    card = entity.get("vcardArray")
    if not isinstance(card, list) or len(card) < 2:
        return None
    for item in card[1]:
        if isinstance(item, list) and len(item) >= 4 and item[0] == field:
            value = item[3]
            if isinstance(value, list):
                value = " ".join(str(v) for v in value if v)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _find(entities: list[dict] | None, role: str) -> dict | None:
    """First entity with this role, searching nested entities too."""
    for entity in entities or []:
        if role in entity.get("roles", []):
            return entity
        found = _find(entity.get("entities"), role)
        if found:
            return found
    return None


def parse_domain(domain: str, data: dict[str, Any]) -> Registration:
    events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
    created = parse_date(events.get("registration"))
    registrar = _find(data.get("entities"), "registrar")
    registrant = _find(data.get("entities"), "registrant")
    abuse = _find(registrar.get("entities"), "abuse") if registrar else None
    return Registration(
        domain=domain,
        source="rdap",
        registrar=_vcard(registrar, "fn") if registrar else None,
        registrar_abuse_email=_vcard(abuse, "email") if abuse else None,
        registrant=(_vcard(registrant, "org") or _vcard(registrant, "fn")) if registrant else None,
        created=created.isoformat() if created else None,
        updated=events.get("last changed"),
        expires=events.get("expiration"),
        age_days=age_days(created),
        nameservers=sorted(
            {n.get("ldhName", "").lower() for n in data.get("nameservers", []) if n.get("ldhName")}
        ),
        flags=[s for s in data.get("status", []) if isinstance(s, str)],
        dnssec=(data.get("secureDNS") or {}).get("delegationSigned"),
    )


async def lookup_domain(domain: str) -> Registration | None:
    """Registration data, or None if the domain's registry has no RDAP server (use WHOIS then)."""
    cached = _domain_cache.get(domain)
    if cached is not None:
        return cached
    base = await domain_server(domain)
    if base is None:
        return None
    try:
        data = await get_json(f"{base}domain/{domain}", accept=RDAP_JSON)
        result = parse_domain(domain, data)
    except NotFound:
        result = Registration(
            domain=domain,
            status="not_found",
            source="rdap",
            note="The registry has no record of this domain.",
        )
    _domain_cache.set(domain, result)
    return result


def parse_ip(ip: str, data: dict[str, Any]) -> Server:
    abuse = _find(data.get("entities"), "abuse")
    start, end = data.get("startAddress"), data.get("endAddress")
    return Server(
        ip=ip,
        network_name=data.get("name"),
        network_range=f"{start} - {end}" if start and end else None,
        country_code=data.get("country"),
        abuse_email=_vcard(abuse, "email") if abuse else None,
    )


async def lookup_ip(ip: str) -> Server | None:
    cached = _ip_cache.get(ip)
    if cached is not None:
        return cached
    base = await ip_server(ip)
    if base is None:
        return None
    result = parse_ip(ip, await get_json(f"{base}ip/{ip}", accept=RDAP_JSON))
    _ip_cache.set(ip, result)
    return result
