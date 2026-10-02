"""HTTP for blacklist lookups. These requests go to the listing services only, never to the scanned
site (safety rule 1), and they never follow redirects."""

import httpx

from app.recon.net import USER_AGENT

# Tests swap in a fake transport here, so no test ever talks to a real service.
transport: httpx.AsyncBaseTransport | None = None


def client(timeout: float = 6) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout, transport=transport, headers={"User-Agent": USER_AGENT}, follow_redirects=False
    )
