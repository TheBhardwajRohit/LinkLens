"""A small HTTP proxy that every browser connection must go through.

For each connection it asks the guard whether the host is allowed, then
connects to the exact IP the guard checked. It also keeps a log of every
connection (allowed or blocked), which becomes the "contacted domains" list,
and it caps how many connections and bytes one visit may use.

Supports CONNECT (used for https:// and wss://) and plain http:// requests.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.guard import Blocked, Guard

MAX_HEADER_BYTES = 64 * 1024
HEADER_TIMEOUT = 10
CONNECT_TIMEOUT = 10
IDLE_TIMEOUT = 30

# Headers that only make sense between the browser and the proxy.
_HOP_BY_HOP = {"proxy-connection", "proxy-authorization", "connection", "keep-alive"}

BLOCKED_HEADER = "X-LinkLens-Blocked"


@dataclass
class ProxyEvent:
    host: str
    port: int
    allowed: bool
    reason: str | None = None
    ip: str | None = None
    at: float = field(default_factory=time.monotonic)


class FilteringProxy:
    def __init__(self, guard: Guard, *, max_connections: int = 300, max_bytes: int = 50 * 1024 * 1024):
        self._guard = guard
        self._max_connections = max_connections
        self._max_bytes = max_bytes
        self._server: asyncio.Server | None = None
        self._tasks: set[asyncio.Task] = set()
        self.events: list[ProxyEvent] = []
        self.bytes_in = 0

    @property
    def budget_exceeded(self) -> bool:
        return self.bytes_in >= self._max_bytes

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._on_client, "127.0.0.1", 0)
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.create_task(self._handle(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream_writer: asyncio.StreamWriter | None = None
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), HEADER_TIMEOUT)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
                return
            if len(head) > MAX_HEADER_BYTES:
                return
            lines = head.decode("latin-1").split("\r\n")
            try:
                method, target, version = lines[0].split(" ", 2)
            except ValueError:
                return

            if method.upper() == "CONNECT":
                host, port = _split_host_port(target, default_port=443)
            else:
                url = urlsplit(target)
                if url.scheme.lower() != "http" or not url.hostname:
                    await _reply(writer, 400, "Bad request")
                    return
                host, port = url.hostname, url.port or 80

            allowed = await self._check(host, port)
            if allowed is None:
                await _reply(writer, 403, "Blocked by the LinkLens sandbox", blocked=True)
                return

            try:
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    asyncio.open_connection(allowed.ip, port), CONNECT_TIMEOUT
                )
            except (OSError, TimeoutError):
                await _reply(writer, 502, "Could not connect")
                return

            if method.upper() == "CONNECT":
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                upstream_writer.write(_rewrite_request(method, target, version, lines[1:]))
                await upstream_writer.drain()

            # Copy bytes both ways. When either side closes, close the other too.
            pipes = {
                asyncio.create_task(self._pipe(reader, upstream_writer, count=False)),
                asyncio.create_task(self._pipe(upstream_reader, writer, count=True)),
            }
            _, pending = await asyncio.wait(pipes, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            for w in (writer, upstream_writer):
                if w is not None:
                    w.close()

    async def _check(self, host: str, port: int):
        if len(self.events) >= self._max_connections:
            self.events.append(ProxyEvent(host, port, False, "too many connections for one visit"))
            return None
        if self.budget_exceeded:
            self.events.append(ProxyEvent(host, port, False, "download size limit reached"))
            return None
        try:
            allowed = await self._guard.check(host, port)
        except Blocked as err:
            self.events.append(ProxyEvent(host.lower(), port, False, str(err)))
            return None
        self.events.append(ProxyEvent(allowed.host, port, True, ip=allowed.ip))
        return allowed

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, *, count: bool) -> None:
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(65536), IDLE_TIMEOUT)
                if not chunk:
                    break
                if count:
                    self.bytes_in += len(chunk)
                    if self.budget_exceeded:
                        break
                writer.write(chunk)
                await writer.drain()
        except (ConnectionError, TimeoutError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()


def _split_host_port(target: str, default_port: int) -> tuple[str, int]:
    if target.startswith("["):
        host, _, rest = target[1:].partition("]")
        port = rest.lstrip(":")
    else:
        host, _, port = target.rpartition(":") if ":" in target else (target, "", "")
    try:
        return host, int(port) if port else default_port
    except ValueError:
        return host, -1


def _rewrite_request(method: str, target: str, version: str, header_lines: list[str]) -> bytes:
    """Turn a proxy request (absolute URL) into a normal one, and ask the server to close after replying."""
    url = urlsplit(target)
    path = (url.path or "/") + (f"?{url.query}" if url.query else "")
    headers = [h for h in header_lines if h and h.split(":", 1)[0].strip().lower() not in _HOP_BY_HOP]
    headers.append("Connection: close")
    return (f"{method} {path} {version}\r\n" + "\r\n".join(headers) + "\r\n\r\n").encode("latin-1")


async def _reply(writer: asyncio.StreamWriter, status: int, text: str, *, blocked: bool = False) -> None:
    body = text.encode()
    marker = f"{BLOCKED_HEADER}: 1\r\n" if blocked else ""
    writer.write(
        f"HTTP/1.1 {status} {text}\r\n{marker}Content-Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
        + body
    )
    with contextlib.suppress(ConnectionError):
        await writer.drain()
