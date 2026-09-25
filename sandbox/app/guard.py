"""SSRF guard: decides which addresses the sandbox may connect to.

SSRF (server-side request forgery) is when a link tricks our server into
reaching places it shouldn't, like our own database or the cloud metadata
service. The guard looks up the real IP address behind every host and only
allows public internet addresses. The filtering proxy calls it for every
single connection the browser makes, and then connects to the exact IP that
was checked, so a DNS answer can't change between the check and the connect.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[list[str]]]

# Ports a web page may use. Low ports other than 80 and 443 (SSH, SMTP, and so on) are blocked.
WEB_PORTS = {80, 443}
MIN_HIGH_PORT = 1024

_METADATA = {ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("fd00:ec2::254")}
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class Blocked(Exception):
    """The connection is not allowed. The message is a plain reason for the report."""


@dataclass(frozen=True)
class Allowed:
    host: str
    port: int
    ip: str


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """IPv6 forms that carry an IPv4 address inside, which could hide a private one."""
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip.sixtofour:
        return ip.sixtofour
    if ip.teredo:
        return ip.teredo[1]
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def ip_block_reason(ip: IPAddress) -> str | None:
    """Why this IP may not be contacted, or None if it's a public internet address."""
    if isinstance(ip, ipaddress.IPv6Address):
        inner = _embedded_ipv4(ip)
        if inner is not None:
            return ip_block_reason(inner)
    if ip in _METADATA:
        return "cloud metadata address"
    if ip.is_loopback:
        return "local address (this machine)"
    if ip.is_unspecified:
        return "unspecified address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_private:
        return "private network address"
    if ip.is_reserved or not ip.is_global:
        return "reserved address"
    return None


def _literal_ip(host: str) -> list[str] | None:
    """The host as a one-item list if it's already an IP address, otherwise None."""
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        return None


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


class Guard:
    """Checks a host and port before any connection.

    `allow` is for tests only: exact (ip, port) pairs that are let through even
    though they're private, so tests can run a local fixture server. It is never
    read from config or the environment.
    """

    def __init__(self, resolver: Resolver = system_resolver, allow: frozenset[tuple[str, int]] = frozenset()):
        self._resolve = resolver
        self._allow = allow

    async def check(self, host: str, port: int) -> Allowed:
        host = host.strip().strip("[]").rstrip(".").lower()
        if not host:
            raise Blocked("empty host")
        if not (port in WEB_PORTS or MIN_HIGH_PORT <= port <= 65535):
            raise Blocked(f"port {port} is not a web port")
        if host == "localhost" or host.endswith(".localhost"):
            raise Blocked("local address (this machine)")

        ips = _literal_ip(host)
        if ips is None:
            try:
                ips = await asyncio.wait_for(self._resolve(host, port), timeout=5)
            except (TimeoutError, OSError):
                ips = []
        if not ips:
            raise Blocked("the domain name could not be found")

        # Every address must be public. A name that points at one public and one
        # private address is blocked, since the browser could pick either.
        for ip in ips:
            if (ip, port) in self._allow:
                continue
            reason = ip_block_reason(ipaddress.ip_address(ip))
            if reason:
                raise Blocked(reason)
        return Allowed(host=host, port=port, ip=ips[0])
