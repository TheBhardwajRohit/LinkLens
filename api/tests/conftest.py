import os

# Before the app is imported: no database setup or downloads at startup during tests.
os.environ["STARTUP_TASKS"] = "false"

import pytest  # noqa: E402

from app import storage  # noqa: E402
from app.ratelimit import limiter  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    """An in-memory stand-in for the database, so tests never need Postgres."""
    saved: dict[str, dict] = {}

    async def save(database_url, result):
        saved[result["id"]] = result

    async def load(database_url, scan_id):
        return saved.get(scan_id)

    monkeypatch.setattr(storage, "save", save)
    monkeypatch.setattr(storage, "load", load)
    limiter.reset()
    return saved
