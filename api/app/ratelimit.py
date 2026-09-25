"""A simple per-address limit on how many scans can be started (safety rule 8).
In memory, so it resets when the API restarts; good enough for one server."""

import time
from collections import deque

WINDOW_S = 3600


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int) -> int | None:
        """None if allowed (and counted); otherwise how many minutes until the next scan is allowed."""
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, int((WINDOW_S - (now - hits[0])) // 60) + 1)
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()
