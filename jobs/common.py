"""Shared helpers for the data jobs. Jobs are plain scripts, so they run the same on GitHub Actions,
in Docker on a PC, or on any server."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg

# The jobs reuse the API's own code (fingerprints, link and page checks), so dataset pages and
# feed pages are read exactly like scanned pages. Run them from the repo root with
# PYTHONPATH=api:. (the jobs image and the workflows set this); the line below covers the rest.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app import cache, pages, storage  # noqa: E402


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def connect() -> psycopg.Connection | None:
    """A database connection with every table in place, or None when no database is configured
    (then the job only reports what it would have stored)."""
    url = database_url()
    if not url:
        return None
    conn = psycopg.connect(url, connect_timeout=15, autocommit=True)
    conn.execute(storage.SCHEMA)
    conn.execute(cache.SCHEMA)
    conn.execute(pages.SCHEMA)
    return conn


def now() -> datetime:
    return datetime.now(UTC)


def say(*parts: object) -> None:
    print(*parts, flush=True)
