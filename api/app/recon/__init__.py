"""Recon: who registered the domain, where the server is, who runs the network, and what the
certificates say. Every source here is a registry, a DNS resolver, a log, or a local database.
None of them is the scanned site, which only the sandbox may contact (safety rule 1)."""

import asyncio
import ipaddress
import time
from collections.abc import Awaitable
from urllib.parse import urlsplit

from app.recon import ct, dns_records, http_info, rdap, whois
from app.recon.domains import is_ip, registered_domain
from app.recon.geoip import geo
from app.recon.models import CertHistory, DnsRecords, Recon, Registration, Server

MAX_CHAIN_DOMAINS = 4


async def _timed[T](coro: Awaitable[T], seconds: float, fallback: T) -> T:
    """Wait for one source, but never longer than `seconds`. On failure, return the fallback
    marked with a plain-words status, so one slow source can't hold up the whole scan."""
    try:
        return await asyncio.wait_for(coro, seconds)
    except TimeoutError:
        if hasattr(fallback, "status"):
            fallback.status = "timeout"  # type: ignore[attr-defined]
            fallback.note = "This source didn't answer in time."  # type: ignore[attr-defined]
        return fallback
    except Exception:
        if hasattr(fallback, "status"):
            fallback.status = "error"  # type: ignore[attr-defined]
            fallback.note = "This source couldn't be reached."  # type: ignore[attr-defined]
        return fallback


async def registration(domain: str) -> Registration:
    """RDAP first; WHOIS only when the registry has no RDAP server."""
    found = await rdap.lookup_domain(domain)
    return found if found is not None else await whois.lookup_domain(domain)


def _public(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


async def server_info(ip: str) -> Server:
    located = geo.lookup(ip)
    owner = await _timed(rdap.lookup_ip(ip), 8, None)
    if owner is not None:
        located.network_name = owner.network_name
        located.network_range = owner.network_range
        located.abuse_email = owner.abuse_email
        located.country_code = located.country_code or owner.country_code
    return located


async def run_recon(visit: dict, requested_url: str) -> Recon:
    started = time.monotonic()
    hops = visit.get("hops") or []
    final_url = visit.get("final_url") or (hops[-1]["url"] if hops else requested_url)
    host = (urlsplit(final_url).hostname or "").lower()
    domain = registered_domain(host)
    recon = Recon(host=host or None, registered_domain=domain)

    chain_domains: list[str] = []
    for hop in hops:
        d = registered_domain((urlsplit(hop.get("url", "")).hostname or "").lower())
        if d and d != domain and d not in chain_domains:
            chain_domains.append(d)
    chain_domains = chain_domains[:MAX_CHAIN_DOMAINS]

    tasks: dict[str, Awaitable] = {}
    if domain:
        tasks["registration"] = _timed(registration(domain), 10, Registration(domain=domain))
        tasks["cert_history"] = _timed(ct.history(domain), 22, CertHistory(domain=domain))
    if host and not is_ip(host):
        tasks["dns"] = _timed(dns_records.lookup(host, domain), 6, DnsRecords(host=host))
    for i, d in enumerate(chain_domains):
        tasks[f"chain{i}"] = _timed(registration(d), 10, Registration(domain=d))

    results = dict(zip(tasks, await asyncio.gather(*tasks.values()), strict=True))
    recon.registration = results.get("registration")
    recon.cert_history = results.get("cert_history")
    recon.dns = results.get("dns")
    recon.chain_domains = [results[k] for k in results if k.startswith("chain")]

    # Prefer the IP the sandbox actually connected to; otherwise the first public DNS answer.
    ip = (visit.get("server_ips") or {}).get(host)
    if not ip and host and is_ip(host):
        ip = host.strip("[]")
    if not ip and recon.dns:
        ip = next((a for a in recon.dns.a + recon.dns.aaaa if _public(a)), None)
    private = ip or next(iter((recon.dns.a + recon.dns.aaaa) if recon.dns else []), None)
    if ip and _public(ip):
        recon.server = await server_info(ip)
    elif private:
        recon.server = Server(
            ip=private,
            status="skipped",
            note=f"The name points to a private address ({private}), so there's no public server to look up.",
        )

    recon.certificate = visit.get("tls")
    recon.http = http_info.analyze(visit.get("headers"), visit.get("html"))
    recon.duration_ms = int((time.monotonic() - started) * 1000)
    return recon
