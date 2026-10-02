"""Saved scans, in Postgres (local now, Supabase later). Screenshots go in their own column."""

import base64
import json
import logging
from typing import Any

import psycopg

from app import cache, pages
from app.redact import redact

log = logging.getLogger("linklens.storage")

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    url TEXT NOT NULL,
    final_url TEXT,
    registered_domain TEXT,
    verdict TEXT NOT NULL,
    score SMALLINT NOT NULL,
    scam_type TEXT,
    result JSONB NOT NULL,
    screenshot BYTEA
);
CREATE INDEX IF NOT EXISTS scans_created_idx ON scans (created_at DESC);
CREATE INDEX IF NOT EXISTS scans_domain_idx ON scans (registered_domain);
"""


# Tables owned by the phase 10 extras. Kept here as plain SQL so storage has no import cycle.
MORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scan_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind TEXT NOT NULL,
    note TEXT,
    verdict TEXT,
    score SMALLINT
);
CREATE INDEX IF NOT EXISTS feedback_scan_idx ON feedback (scan_id);
CREATE TABLE IF NOT EXISTS api_keys (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash BYTEA NOT NULL UNIQUE,
    scans_per_hour INTEGER NOT NULL DEFAULT 200,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked BOOLEAN NOT NULL DEFAULT false
);
"""


async def init(database_url: str) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(SCHEMA)
        await conn.execute(cache.SCHEMA)
        await conn.execute(pages.SCHEMA)
        await conn.execute(MORE_SCHEMA)


async def save(database_url: str, result: dict[str, Any]) -> None:
    stored = redact(json.loads(json.dumps(result)))
    shot = stored["visit"].pop("screenshot_jpeg_b64", None)
    analysis = stored["analysis"]
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        await conn.execute(
            """INSERT INTO scans (id, created_at, url, final_url, registered_domain, verdict, score,
                                  scam_type, result, screenshot)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (
                stored["id"],
                stored["created_at"],
                stored["url"],
                stored["visit"].get("final_url"),
                stored["recon"].get("registered_domain"),
                analysis["verdict"],
                analysis["score"],
                (analysis.get("scam_type") or {}).get("id"),
                json.dumps(stored),
                base64.b64decode(shot) if shot else None,
            ),
        )


async def load(database_url: str, scan_id: str) -> dict[str, Any] | None:
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute("SELECT result, screenshot FROM scans WHERE id = %s", (scan_id,))
        row = await cur.fetchone()
    if row is None:
        return None
    result, shot = row
    result = result if isinstance(result, dict) else json.loads(result)
    result["visit"]["screenshot_jpeg_b64"] = base64.b64encode(shot).decode() if shot else None
    result["saved"] = True
    return result
