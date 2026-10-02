"""A small lookup cache, so repeat scans don't spend free quotas (VirusTotal allows 500 checks a day).

Memory first. When a database is configured, entries also survive restarts in the `lookup_cache`
table. A database problem never breaks a scan: the cache just falls back to memory.
"""

import json
import logging
import time
from typing import Any

import psycopg

log = logging.getLogger("linklens.cache")

SCHEMA = """
CREATE TABLE IF NOT EXISTS lookup_cache (
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (source, key)
);
CREATE INDEX IF NOT EXISTS lookup_cache_expires_idx ON lookup_cache (expires_at);
"""
MAX_ITEMS = 5000
MEMORY_ONLY = {"stats"}

_memory: dict[tuple[str, str], tuple[float, Any]] = {}
_database_url: str | None = None


def configure(database_url: str | None) -> None:
    global _database_url
    _database_url = database_url


def clear() -> None:
    _memory.clear()


def remember(source: str, key: str, value: Any, ttl_s: float) -> None:
    """Memory only, for short-lived things that aren't worth a database row."""
    if len(_memory) >= MAX_ITEMS:
        _memory.pop(next(iter(_memory)))
    _memory[(source, key)] = (time.time() + ttl_s, value)


async def get(source: str, key: str) -> Any | None:
    item = _memory.get((source, key))
    if item is not None:
        if item[0] > time.time():
            return item[1]
        _memory.pop((source, key), None)
    if not _database_url or source in MEMORY_ONLY:
        return None
    try:
        async with await psycopg.AsyncConnection.connect(_database_url, connect_timeout=3) as conn:
            cur = await conn.execute(
                """SELECT value, EXTRACT(EPOCH FROM expires_at - now()) FROM lookup_cache
                   WHERE source = %s AND key = %s AND expires_at > now()""",
                (source, key),
            )
            row = await cur.fetchone()
    except Exception as err:
        log.warning("cache read failed: %s", type(err).__name__)
        return None
    if row is None:
        return None
    value = row[0] if not isinstance(row[0], str) else json.loads(row[0])
    remember(source, key, value, float(row[1]))
    return value


async def put(source: str, key: str, value: Any, ttl_s: float) -> None:
    remember(source, key, value, ttl_s)
    if not _database_url:
        return
    try:
        async with await psycopg.AsyncConnection.connect(_database_url, connect_timeout=3) as conn:
            await conn.execute(
                """INSERT INTO lookup_cache (source, key, value, expires_at)
                   VALUES (%s, %s, %s, now() + make_interval(secs => %s))
                   ON CONFLICT (source, key) DO UPDATE
                   SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at""",
                (source, key, json.dumps(value), ttl_s),
            )
    except Exception as err:
        log.warning("cache write failed: %s", type(err).__name__)


async def sweep() -> None:
    """Drop expired rows. Called now and then so the table stays small."""
    if not _database_url:
        return
    try:
        async with await psycopg.AsyncConnection.connect(_database_url, connect_timeout=3) as conn:
            await conn.execute("DELETE FROM lookup_cache WHERE expires_at < now()")
    except Exception as err:
        log.warning("cache sweep failed: %s", type(err).__name__)
