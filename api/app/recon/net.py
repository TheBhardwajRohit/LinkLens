"""Small, careful HTTP helpers for recon sources (registries, crt.sh, and so on).
None of these ever request the scanned site itself; only the sandbox does that."""

import json
import time
from typing import Any

import httpx

USER_AGENT = "LinkLens/0.1 (+https://github.com/TheBhardwajRohit/LinkLens)"


class NotFound(Exception):
    pass


class RateLimited(Exception):
    pass


class TooLarge(Exception):
    pass


async def get_json(
    url: str, *, timeout: float = 8, max_bytes: int = 2_000_000, accept: str = "application/json"
) -> Any:
    """GET a JSON document, following at most 3 redirects and refusing oversized replies."""
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, max_redirects=3) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code == 404:
                raise NotFound(url)
            if resp.status_code == 429:
                raise RateLimited(url)
            resp.raise_for_status()
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body += chunk
                if len(body) > max_bytes:
                    raise TooLarge(url)
    return json.loads(body)


class TTLCache:
    """A tiny in-memory cache, so repeat scans don't hammer free services. Phase 4 moves this to the DB."""

    def __init__(self, ttl_s: float, max_items: int = 1000):
        self._ttl = ttl_s
        self._max = max_items
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None or item[0] < time.monotonic():
            self._items.pop(key, None)
            return None
        return item[1]

    def set(self, key: str, value: Any) -> None:
        if len(self._items) >= self._max:
            self._items.pop(next(iter(self._items)))
        self._items[key] = (time.monotonic() + self._ttl, value)
