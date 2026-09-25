"""Plain WHOIS (port 43), used only for domains whose registry has no RDAP yet (.io, .co, ...).
IANA's WHOIS tells us which server to ask; that server's answer is free text, so parsing is best effort."""

import asyncio
import re

from app.recon.domains import age_days, parse_date
from app.recon.models import Registration
from app.recon.net import TTLCache

MAX_REPLY = 200_000
_cache = TTLCache(6 * 3600)

_FIELDS = {
    "created": r"(?:creation date|created on|created|registered on|registration time|domain registered)",
    "expires": (
        r"(?:registry expiry date|registrar registration expiration date"
        r"|expiration date|expiry date|expires on|expires|paid-till)"
    ),
    "updated": r"(?:updated date|last updated|last modified|changed)",
    "registrar": r"(?:registrar|sponsoring registrar|registrar name)",
}
_NS = re.compile(r"^\s*(?:name server|nserver|nameserver)s?:\s*(\S+)", re.I | re.M)
_STATUS = re.compile(r"^\s*(?:domain )?status:\s*(\S+)", re.I | re.M)
_NOT_FOUND = re.compile(
    r"no match|not found|no data found|no entries found|status:\s*free|is available", re.I
)


async def query(server: str, text: str, timeout: float = 8) -> str:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(server, 43), timeout)
    try:
        writer.write(text.encode("idna") + b"\r\n")
        await writer.drain()
        reply = bytearray()
        while len(reply) < MAX_REPLY:
            chunk = await asyncio.wait_for(reader.read(8192), timeout)
            if not chunk:
                break
            reply += chunk
        return reply.decode("utf-8", "replace")
    finally:
        writer.close()


def _field(text: str, pattern: str) -> str | None:
    m = re.search(rf"^\s*{pattern}\s*:\s*(.+?)\s*$", text, re.I | re.M)
    return m.group(1) if m and m.group(1).strip() else None


def parse(domain: str, text: str) -> Registration:
    if _NOT_FOUND.search(text[:2000]) and not _field(text, _FIELDS["created"]):
        return Registration(
            domain=domain,
            status="not_found",
            source="whois",
            note="The registry has no record of this domain.",
        )
    created = parse_date(_field(text, _FIELDS["created"]))
    expires = parse_date(_field(text, _FIELDS["expires"]))
    updated = parse_date(_field(text, _FIELDS["updated"]))
    return Registration(
        domain=domain,
        source="whois",
        registrar=_field(text, _FIELDS["registrar"]),
        created=created.isoformat() if created else None,
        expires=expires.isoformat() if expires else None,
        updated=updated.isoformat() if updated else None,
        age_days=age_days(created),
        nameservers=sorted({ns.lower().rstrip(".") for ns in _NS.findall(text)}),
        flags=sorted(set(_STATUS.findall(text)))[:10],
    )


async def lookup_domain(domain: str) -> Registration:
    cached = _cache.get(domain)
    if cached is not None:
        return cached
    tld = domain.rsplit(".", 1)[-1]
    iana = await query("whois.iana.org", tld)
    m = re.search(r"^\s*(?:refer|whois):\s*(\S+)", iana, re.I | re.M)
    if not m:
        return Registration(
            domain=domain, status="not_configured", note="This registry offers no public WHOIS."
        )
    result = parse(domain, await query(m.group(1), domain))
    _cache.set(domain, result)
    return result
