import os

# Before the app is imported: no database setup or downloads at startup during tests.
os.environ["STARTUP_TASKS"] = "false"

import pytest  # noqa: E402

from app import blacklists, cache, storage  # noqa: E402
from app.blacklists import virustotal  # noqa: E402
from app.blacklists.models import Blacklists  # noqa: E402
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


@pytest.fixture(autouse=True)
def no_outside_lookups(monkeypatch, request):
    """Scans in tests never ask real blacklist services. Tests of the blacklist code itself carry
    the `real_blacklists` mark and bring their own fake HTTP transport."""
    cache.configure(None)
    cache.clear()
    virustotal.reset()
    if "real_blacklists" in request.keywords:
        return

    async def nothing_listed(urls, settings, **kwargs):
        return Blacklists(checked=urls)

    monkeypatch.setattr(blacklists, "check", nothing_listed)
