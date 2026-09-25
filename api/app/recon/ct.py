"""Certificate Transparency: every public TLS certificate is logged. Searching the logs shows when
certificates for a domain first appeared, and which other names were put on the same certificates.

crt.sh has the full history but is often slow or down; Cert Spotter (free, limited, current
certificates only) is the backup.
"""

from urllib.parse import quote

from app.recon.domains import registered_domain
from app.recon.models import CertHistory
from app.recon.net import TooLarge, TTLCache, get_json

MAX_NAMES = 30
_cache = TTLCache(24 * 3600)


def summarize(domain: str, certs: list[dict], source: str) -> CertHistory:
    """certs: dicts with 'names' (list), 'not_before' (ISO), 'issuer' (str)."""
    subdomains: set[str] = set()
    others: set[str] = set()
    issuers: dict[str, int] = {}
    dates = []
    for cert in certs:
        if cert.get("not_before"):
            dates.append(cert["not_before"])
        if cert.get("issuer"):
            issuers[cert["issuer"]] = issuers.get(cert["issuer"], 0) + 1
        for raw in cert.get("names", []):
            name = raw.strip().lower().removeprefix("*.")
            if not name or name == domain:
                continue
            if name.endswith("." + domain):
                subdomains.add(name)
            else:
                reg = registered_domain(name)
                if reg and reg != domain:
                    others.add(reg)
    dates.sort()
    return CertHistory(
        domain=domain,
        source=source,
        cert_count=len(certs),
        first_seen=dates[0] if dates else None,
        latest=dates[-1] if dates else None,
        issuers=[name for name, _ in sorted(issuers.items(), key=lambda kv: -kv[1])[:3]],
        subdomains=sorted(subdomains)[:MAX_NAMES],
        other_domains=sorted(others)[:MAX_NAMES],
        note=None
        if source == "crt.sh"
        else "Current certificates only (the full history service was unavailable).",
    )


def _issuer_org(issuer_name: str) -> str | None:
    for part in issuer_name.split(","):
        key, _, value = part.strip().partition("=")
        if key == "O" and value:
            return value.strip('"')
    return None


async def _crtsh(domain: str) -> CertHistory:
    rows = await get_json(f"https://crt.sh/?q={quote(domain)}&output=json", timeout=12, max_bytes=4_000_000)
    seen: dict[int, dict] = {}
    for row in rows:
        seen.setdefault(
            row.get("id"),
            {
                "names": str(row.get("name_value", "")).split("\n"),
                "not_before": row.get("not_before"),
                "issuer": _issuer_org(str(row.get("issuer_name", ""))),
            },
        )
    return summarize(domain, list(seen.values()), "crt.sh")


async def _certspotter(domain: str) -> CertHistory:
    url = (
        f"https://api.certspotter.com/v1/issuances?domain={quote(domain)}"
        "&include_subdomains=true&expand=dns_names&expand=issuer"
    )
    rows = await get_json(url, timeout=10)
    certs = [
        {
            "names": row.get("dns_names", []),
            "not_before": row.get("not_before"),
            "issuer": (row.get("issuer") or {}).get("friendly_name"),
        }
        for row in rows
    ]
    return summarize(domain, certs, "certspotter")


async def history(domain: str) -> CertHistory:
    cached = _cache.get(domain)
    if cached is not None:
        return cached
    try:
        result = await _crtsh(domain)
    except TooLarge:
        result = CertHistory(
            domain=domain,
            status="skipped",
            source="crt.sh",
            note="Too many certificates to list (a very large site).",
        )
    except Exception:  # crt.sh is often slow or down; try the backup
        try:
            result = await _certspotter(domain)
        except Exception:
            return CertHistory(
                domain=domain, status="error", note="Both certificate history services were unavailable."
            )
    _cache.set(domain, result)
    return result
