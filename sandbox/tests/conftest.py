"""Test fixtures. Everything here is local and made up. Tests never touch real scam links.

A tiny web server on 127.0.0.1 serves safe test pages. Test hostnames are
resolved by a fake resolver:

    site.test   -> 127.0.0.1 (allowed, only on the fixture server's port)
    rebind.test -> 127.0.0.2 (NOT allowed: a public-looking name that points at this machine)
    mixed.test  -> 93.184.215.14 and 10.0.0.1 (one public, one private)
    anything else -> "not found"
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.guard import Guard

PAGES = {
    "/plain": "<title>Plain page</title><h1>Hello from the fixture server</h1>",
    "/meta": '<title>Meta</title><meta http-equiv="refresh" content="0; url=/plain">Redirecting',
    "/meta-later": '<title>Later</title><meta http-equiv="refresh" content="30;url=/plain">Wait',
    "/js": "<title>JS</title><script>location.href = '/plain'</script>",
    "/chain-meta": '<meta http-equiv="refresh" content="0;url=/js">',
    "/js-to-private": "<script>location.href = 'http://10.0.0.1/admin'</script>",
    "/js-to-rebind": "<script>location.href = 'http://rebind.test:{port}/plain'</script>",
    "/images": (
        "<title>Images</title><h1>Page with blocked images</h1>"
        '<img src="http://10.0.0.1/a.png"><img src="http://169.254.169.254/latest/meta-data/">'
        '<img src="/plain">'
    ),
    "/form": (
        "<title>Login</title><form method=post action=/steal>"
        "<input name=user value=x><input type=password name=pass value=y>"
        "<button>Sign in</button></form><script>setTimeout(() => {}, 10)</script>"
    ),
    "/captcha": '<title>Just a moment</title><div class="g-recaptcha" data-sitekey="x"></div>',
    "/popup": "<title>Popup</title><script>window.open('/plain')</script>",
    "/alert": "<title>Alert</title><script>alert('hi'); location.href = '/plain'</script>",
    # The page's own script submits a form (GET). We never submit anything ourselves.
    "/autoform": (
        "<form id=f action=/plain method=get><input name=q value=1></form><script>f.submit()</script>"
    ),
}

REDIRECTS = {
    "/r302": (302, "/r301"),
    "/r301": (301, "/plain"),
    "/mixed-chain": (302, "/chain-meta"),
    "/to-private": (302, "http://10.0.0.1/"),
    "/to-metadata": (302, "http://169.254.169.254/latest/meta-data/"),
    "/to-rebind": (302, "http://rebind.test:{port}/plain"),
    "/to-ssh": (302, "http://site.test:22/"),
}


class FixtureServer:
    def __init__(self):
        self.posts: list[str] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status: int, body: bytes = b"", headers: dict | None = None):
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                port = str(server.port)
                path = self.path.split("?")[0]
                if path in REDIRECTS:
                    status, location = REDIRECTS[path]
                    self._send(status, headers={"Location": location.replace("{port}", port)})
                elif path in PAGES:
                    body = PAGES[path].replace("{port}", port).encode()
                    self._send(200, body, {"Content-Type": "text/html; charset=utf-8"})
                elif path == "/refresh-header":
                    self._send(
                        200,
                        b"<title>Refresh</title>",
                        {"Content-Type": "text/html", "Refresh": "0; url=/plain"},
                    )
                elif path == "/download":
                    self._send(
                        200,
                        b"MZ not really a program",
                        {
                            "Content-Type": "application/octet-stream",
                            "Content-Disposition": "attachment; filename=invoice.exe",
                        },
                    )
                elif path == "/slow":
                    time.sleep(8)
                    self._send(200, b"<title>Slow</title>", {"Content-Type": "text/html"})
                else:
                    self._send(404, b"not found")

            def do_POST(self):
                server.posts.append(self.path)
                self._send(200, b"ok")

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def url(self, path: str, host: str = "site.test") -> str:
        return f"http://{host}:{self.port}{path}"

    def start(self):
        self._thread.start()

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()


def fake_resolver(mapping: dict[str, list[str]]):
    async def resolve(host: str, port: int) -> list[str]:
        if host in mapping:
            return mapping[host]
        raise OSError(f"{host} not found")

    return resolve


RESOLVE = {
    "site.test": ["127.0.0.1"],
    "rebind.test": ["127.0.0.2"],
    "mixed.test": ["93.184.215.14", "10.0.0.1"],
}


@pytest.fixture(scope="session")
def fixture_server():
    server = FixtureServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def guard(fixture_server):
    # Only the fixture server's exact address and port get through. Every other private address is blocked.
    return Guard(resolver=fake_resolver(RESOLVE), allow=frozenset({("127.0.0.1", fixture_server.port)}))


@pytest.fixture
def anyio_backend():
    return "asyncio"
