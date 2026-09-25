import asyncio

import pytest

from app.guard import Guard
from app.proxy import BLOCKED_HEADER, FilteringProxy
from tests.conftest import RESOLVE, fake_resolver

pytestmark = pytest.mark.anyio


async def _raw(port: int, request: str) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(request.encode())
    await writer.drain()
    data = await asyncio.wait_for(reader.read(65536), 5)
    writer.close()
    return data


async def test_allowed_http_request_is_forwarded(guard, fixture_server):
    proxy = FilteringProxy(guard)
    port = await proxy.start()
    try:
        url = fixture_server.url("/plain")
        data = await _raw(port, f"GET {url} HTTP/1.1\r\nHost: site.test\r\n\r\n")
        assert data.startswith(b"HTTP/1.0 200") or data.startswith(b"HTTP/1.1 200")
        assert proxy.events[0].allowed and proxy.events[0].host == "site.test"
    finally:
        await proxy.stop()


async def test_connect_to_private_ip_is_refused(guard):
    proxy = FilteringProxy(guard)
    port = await proxy.start()
    try:
        data = await _raw(port, "CONNECT 10.0.0.1:443 HTTP/1.1\r\nHost: 10.0.0.1:443\r\n\r\n")
        assert data.startswith(b"HTTP/1.1 403")
        assert BLOCKED_HEADER.encode() in data
        assert proxy.events[0].allowed is False
    finally:
        await proxy.stop()


async def test_connect_to_metadata_is_refused(guard):
    proxy = FilteringProxy(guard)
    port = await proxy.start()
    try:
        data = await _raw(port, "CONNECT 169.254.169.254:80 HTTP/1.1\r\n\r\n")
        assert data.startswith(b"HTTP/1.1 403")
        assert proxy.events[0].reason == "cloud metadata address"
    finally:
        await proxy.stop()


async def test_rebinding_name_is_refused(guard, fixture_server):
    proxy = FilteringProxy(guard)
    port = await proxy.start()
    try:
        data = await _raw(port, f"GET http://rebind.test:{fixture_server.port}/plain HTTP/1.1\r\n\r\n")
        assert data.startswith(b"HTTP/1.1 403")
    finally:
        await proxy.stop()


async def test_connection_cap(fixture_server):
    guard = Guard(resolver=fake_resolver(RESOLVE), allow=frozenset({("127.0.0.1", fixture_server.port)}))
    proxy = FilteringProxy(guard, max_connections=1)
    port = await proxy.start()
    try:
        url = fixture_server.url("/plain")
        first = await _raw(port, f"GET {url} HTTP/1.1\r\n\r\n")
        second = await _raw(port, f"GET {url} HTTP/1.1\r\n\r\n")
        assert b"200" in first.split(b"\r\n")[0]
        assert second.startswith(b"HTTP/1.1 403")
        assert proxy.events[-1].reason == "too many connections for one visit"
    finally:
        await proxy.stop()
