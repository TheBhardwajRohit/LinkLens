"""Health checks for the services the API depends on.

Each check returns "ok" or "unreachable" and never raises.
"""

import httpx
import psycopg


def database(url: str) -> str:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except Exception:
        return "unreachable"


def sandbox(url: str) -> str:
    # Talks only to our own sandbox service, never to a target URL.
    try:
        resp = httpx.get(f"{url.rstrip('/')}/health", timeout=2)
        return "ok" if resp.status_code == 200 and resp.json().get("status") == "ok" else "unreachable"
    except Exception:
        return "unreachable"
