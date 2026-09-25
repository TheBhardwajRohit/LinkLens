"""Open a link in a locked-down browser and record what happens.

Rules this module follows (see CLAUDE.md, safety rules):
- Every connection goes through the filtering proxy, which applies the SSRF guard.
- Never type, click, submit forms, or accept downloads. Dialogs are dismissed.
- Never try to get past a CAPTCHA or bot check. Detect it and say so.
- Hard time limits on everything.
"""

import asyncio
import base64
import contextlib
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Request, Response, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from pydantic import BaseModel

from app.guard import Blocked, Guard
from app.proxy import BLOCKED_HEADER, FilteringProxy

VIEWPORT = {"width": 1280, "height": 800}
MAX_HTML_BYTES = 2 * 1024 * 1024
NOT_FOUND = "the domain name could not be found"

CHROMIUM_ARGS = [
    "--disable-dev-shm-usage",
    # UDP traffic can't go through the proxy, so turn off everything that uses it.
    "--disable-quic",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--disable-background-networking",
    "--disable-sync",
    "--no-first-run",
    "--mute-audio",
]

BOT_CHECKS = [
    (
        "Cloudflare challenge",
        re.compile(r"challenges\.cloudflare\.com|cf-chl-|cf_chl_|/cdn-cgi/challenge-platform", re.I),
    ),
    ("reCAPTCHA", re.compile(r"google\.com/recaptcha|recaptcha/api\.js|class=[\"'][^\"']*g-recaptcha", re.I)),
    ("hCaptcha", re.compile(r"hcaptcha\.com|class=[\"'][^\"']*h-captcha", re.I)),
]

_META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
_REFRESH = re.compile(r"http-equiv\s*=\s*[\"']?refresh", re.I)
_CONTENT = re.compile(r"content\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.I)
_REFRESH_URL = re.compile(r"^\s*\d*\s*[;,]?\s*(?:url\s*=\s*)?[\"']?([^\"']*)", re.I)

# Why Chromium started a navigation (from its debugging protocol), mapped to our hop kinds.
_NAV_REASONS = {
    "metaTagRefresh": "meta",
    "scriptInitiated": "script",
    "anchorClick": "script",  # we never click, so a click can only come from the page's own script
    "httpHeaderRefresh": "header",
    "formSubmissionGet": "form",
    "formSubmissionPost": "form",
}


@dataclass
class Limits:
    nav_timeout_s: float = 20
    settle_deadline_s: float = 35  # from the start, for the first page plus any later redirects
    hard_timeout_s: float = 60  # absolute cap on the whole visit
    max_hops: int = 10


class Hop(BaseModel):
    url: str
    kind: str  # start | server | header | meta | script | form | page
    status: int | None = None
    blocked: bool = False
    reason: str | None = None


class BlockedRequest(BaseModel):
    host: str
    port: int
    reason: str


class VisitResult(BaseModel):
    requested_url: str
    final_url: str | None = None
    title: str | None = None
    status: int | None = None
    hops: list[Hop] = []
    blocked: list[BlockedRequest] = []
    contacted_domains: list[str] = []
    screenshot_jpeg_b64: str | None = None
    html: str | None = None
    html_truncated: bool = False
    bot_check: str | None = None
    downloads: list[str] = []
    popups: list[str] = []
    pending_refresh: str | None = None
    # None means the visit finished normally. Otherwise:
    # timeout | blocked | unreachable | download | crashed | error
    stopped: str | None = None
    notes: list[str] = []
    duration_ms: int = 0


def find_meta_refresh(html: str) -> str | None:
    """The target of a <meta http-equiv="refresh"> tag, or None if there isn't one."""
    for tag in _META_TAG.findall(html[:500_000]):
        if not _REFRESH.search(tag):
            continue
        m = _CONTENT.search(tag)
        if not m:
            continue
        value = next(g for g in m.groups() if g is not None)
        target = _REFRESH_URL.match(value)
        return target.group(1).strip() if target else ""
    return None


def detect_bot_check(html: str, frame_urls: list[str]) -> str | None:
    haystack = html[:1_000_000] + "\n" + "\n".join(frame_urls)
    for name, pattern in BOT_CHECKS:
        if pattern.search(haystack):
            return name
    return None


class _Recorder:
    """Watches main-frame navigations so we can rebuild the redirect chain."""

    def __init__(self, page: Page, result: VisitResult):
        self.page = page
        self.result = result
        self.nav: list[Request] = []
        self.status: dict[int, int] = {}
        self.blocked: set[int] = set()
        self.failed: dict[int, str] = {}
        self.read_docs: set[str] = set()
        self.meta_docs: set[str] = set()
        self.reasons: list[tuple[str, str]] = []  # (url, kind) for page-started navigations, in order
        self._reads: set[asyncio.Task] = set()

    async def attach(self, context: BrowserContext) -> None:
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)
        self.page.on("requestfailed", self._on_failed)
        # Ask Chromium why each main-frame navigation started. If this fails, the HTML check is the backup.
        with contextlib.suppress(PlaywrightError, KeyError):
            cdp = await context.new_cdp_session(self.page)
            await cdp.send("Page.enable")
            tree = await cdp.send("Page.getFrameTree")
            main_id = tree["frameTree"]["frame"]["id"]

            def on_nav(params: dict) -> None:
                kind = _NAV_REASONS.get(params.get("reason", ""))
                if params.get("frameId") == main_id and kind:
                    self.reasons.append((params.get("url", ""), kind))

            cdp.on("Page.frameRequestedNavigation", on_nav)

    def _is_main_nav(self, request: Request) -> bool:
        try:
            return request.is_navigation_request() and request.frame == self.page.main_frame
        except PlaywrightError:
            return False

    def _on_request(self, request: Request) -> None:
        if self._is_main_nav(request):
            self.nav.append(request)

    def _on_response(self, response: Response) -> None:
        request = response.request
        if not self._is_main_nav(request):
            return
        self.status[id(request)] = response.status
        if response.headers.get(BLOCKED_HEADER.lower()):
            self.blocked.add(id(request))
        elif 200 <= response.status < 300:
            task = asyncio.create_task(self._read_doc(response))
            self._reads.add(task)
            task.add_done_callback(self._reads.discard)

    def _on_failed(self, request: Request) -> None:
        if self._is_main_nav(request):
            self.failed[id(request)] = request.failure or ""

    async def _read_doc(self, response: Response) -> None:
        # Read each page's HTML so we can tell a meta refresh apart from a script redirect.
        with contextlib.suppress(PlaywrightError):
            body = await response.text()
            self.read_docs.add(response.url)
            if find_meta_refresh(body) is not None:
                self.meta_docs.add(response.url)

    async def finish(self) -> None:
        if self._reads:
            await asyncio.wait(self._reads, timeout=2)

    def _page_redirect_kind(self, url: str, prev_url: str, reasons: list[tuple[str, str]]) -> str:
        target = url.split("#")[0]
        for i, (reason_url, kind) in enumerate(reasons):
            if reason_url.split("#")[0] == target:
                del reasons[: i + 1]
                return kind
        if prev_url in self.meta_docs:
            return "meta"
        return "script" if prev_url in self.read_docs else "page"

    def hops(self, proxy: FilteringProxy) -> list[Hop]:
        blocked_hosts = {e.host: e.reason for e in proxy.events if not e.allowed}
        reasons = list(self.reasons)
        hops: list[Hop] = []
        for i, request in enumerate(self.nav):
            if i == 0:
                kind = "start"
            elif request.redirected_from is not None:
                kind = "server"
            else:
                kind = self._page_redirect_kind(request.url, self.nav[i - 1].url, reasons)
            parts = urlsplit(request.url)
            host = (parts.hostname or "").lower()
            key = id(request)
            failure = self.failed.get(key)
            reason = None
            if key in self.blocked or (failure is not None and host in blocked_hosts):
                reason = blocked_hosts.get(host) or "blocked"
            elif failure and "ERR_UNSAFE_PORT" in failure:
                # Chromium refuses some ports (like 22 for SSH) on its own, before our proxy sees them.
                reason = f"port {parts.port} is not a web port"
            hops.append(
                Hop(
                    url=request.url,
                    kind=kind,
                    status=None if reason else self.status.get(key),
                    blocked=reason is not None,
                    reason=reason,
                )
            )
        return hops


def _user_agent(browser: Browser) -> str:
    # A normal desktop Chrome string for the same version. Headless Chrome announces itself
    # as "HeadlessChrome", and many scam kits show a harmless page to anything that does.
    major = browser.version.split(".")[0]
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


async def _settle(page: Page, rec: _Recorder, deadline: float, max_hops: int) -> None:
    """Give late redirects (meta refresh, scripts) a chance to happen, within the deadline."""

    def ms_left(cap: float) -> float:
        return max(min(deadline - time.monotonic(), cap), 0.001) * 1000

    seen = len(rec.nav)
    for _ in range(max_hops):
        if time.monotonic() >= deadline:
            break
        with contextlib.suppress(PlaywrightError):
            await page.wait_for_load_state("load", timeout=ms_left(15))
        with contextlib.suppress(PlaywrightError):
            await page.wait_for_load_state("networkidle", timeout=ms_left(3))
        await asyncio.sleep(ms_left(1.5) / 1000)
        if len(rec.nav) == seen or len(rec.nav) > max_hops:
            break
        seen = len(rec.nav)


async def _browse(
    url: str, proxy_port: int, proxy: FilteringProxy, result: VisitResult, limits: Limits
) -> None:
    started = time.monotonic()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=CHROMIUM_ARGS,
            # "<-loopback>" stops Chromium from skipping the proxy for localhost addresses.
            proxy={"server": f"http://127.0.0.1:{proxy_port}", "bypass": "<-loopback>"},
        )
        try:
            context = await browser.new_context(
                viewport=VIEWPORT,
                accept_downloads=False,
                service_workers="block",
                ignore_https_errors=True,  # scam sites often have bad certificates; phase 3 checks TLS itself
                user_agent=_user_agent(browser),
                locale="en-US",
            )
            page = await context.new_page()
            page.set_default_timeout(10_000)
            rec = _Recorder(page, result)
            await rec.attach(context)

            def on_popup(popup: Page) -> None:
                if popup.url and popup.url != "about:blank":
                    result.popups.append(popup.url)
                asyncio.create_task(popup.close())

            page.on("popup", on_popup)
            page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))
            page.on("download", lambda d: result.downloads.append(d.url))

            def on_crash(_: Page) -> None:
                result.stopped = "crashed"

            page.on("crash", on_crash)

            try:
                await page.goto(url, wait_until="load", timeout=limits.nav_timeout_s * 1000)
            except PlaywrightTimeout:
                result.stopped = "timeout"
            except PlaywrightError as err:
                result.stopped = "download" if "Download is starting" in str(err) else "error"

            if result.stopped is None:
                await _settle(page, rec, started + limits.settle_deadline_s, limits.max_hops)
            await rec.finish()

            result.hops = rec.hops(proxy)
            last = result.hops[-1] if result.hops else None
            if last and last.blocked:
                result.stopped = "unreachable" if last.reason == NOT_FOUND else "blocked"
            elif result.stopped == "error" and last and last.status is None:
                result.stopped = "unreachable"
            if len(result.hops) > limits.max_hops:
                result.notes.append(
                    f"The link kept redirecting, so we stopped after {limits.max_hops} jumps."
                )

            if result.stopped not in ("blocked", "unreachable", "crashed", "download"):
                await _capture(page, result)
        finally:
            with contextlib.suppress(Exception):
                await browser.close()


async def _capture(page: Page, result: VisitResult) -> None:
    with contextlib.suppress(PlaywrightError):
        shot = await page.screenshot(type="jpeg", quality=70, timeout=10_000)
        result.screenshot_jpeg_b64 = base64.b64encode(shot).decode()
    html = ""
    with contextlib.suppress(PlaywrightError):
        html = await page.content()
        data = html.encode("utf-8", "replace")
        if len(data) > MAX_HTML_BYTES:
            html = data[:MAX_HTML_BYTES].decode("utf-8", "ignore")
            result.html_truncated = True
        result.html = html
    with contextlib.suppress(PlaywrightError):
        result.title = (await page.title())[:300] or None
    if page.url.startswith(("http://", "https://")):
        result.final_url = page.url
    if result.hops:
        result.status = result.hops[-1].status

    frame_urls = [f.url for f in page.frames]
    result.bot_check = detect_bot_check(html, frame_urls)
    refresh = find_meta_refresh(html)
    if refresh and result.final_url:
        result.pending_refresh = urljoin(result.final_url, refresh)


def _summarize_network(result: VisitResult, proxy: FilteringProxy) -> None:
    result.contacted_domains = sorted({e.host for e in proxy.events if e.allowed})
    seen: set[tuple[str, int]] = set()
    for e in proxy.events:
        if not e.allowed and (e.host, e.port) not in seen:
            seen.add((e.host, e.port))
            result.blocked.append(BlockedRequest(host=e.host, port=e.port, reason=e.reason or "blocked"))
    if proxy.budget_exceeded:
        result.notes.append("The page tried to load more than 50 MB, so we cut it off.")


def _explain(result: VisitResult) -> None:
    messages = {
        "timeout": "The page took too long to load, so we stopped. The results may be partial.",
        "unreachable": "The site didn't respond. It may be down or already taken offline.",
        "download": "The link tries to download a file. We never download files, so there's no page to show.",
        "crashed": "The page crashed the sandbox browser, so there's no screenshot.",
        "error": "The page could not be opened.",
    }
    if result.stopped == "blocked":
        reason = next((h.reason for h in reversed(result.hops) if h.blocked), None) or "private address"
        result.notes.insert(
            0, f"We stopped because the link leads to a {reason}. LinkLens only visits public websites."
        )
    elif result.stopped in messages:
        result.notes.insert(0, messages[result.stopped])
    if result.bot_check:
        result.notes.append(
            f"The page shows a bot check ({result.bot_check}). We never try to get past these, "
            "so the screenshot may show the check instead of the real page."
        )
    if result.downloads and result.stopped != "download":
        result.notes.append("The page tried to start a download. We blocked it.")
    if result.popups:
        result.notes.append("The page tried to open a popup window. We closed it.")


async def visit(url: str, guard: Guard, limits: Limits | None = None) -> VisitResult:
    limits = limits or Limits()
    result = VisitResult(requested_url=url)
    started = time.monotonic()

    parts = urlsplit(url)
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        port = -1
    if parts.scheme not in ("http", "https") or not parts.hostname:
        result.stopped = "error"
        result.notes.append("Only http and https links can be visited.")
        return result

    # Check the first address before starting a browser at all.
    try:
        await guard.check(parts.hostname, port)
    except Blocked as err:
        result.hops = [Hop(url=url, kind="start", blocked=True, reason=str(err))]
        result.blocked = [BlockedRequest(host=parts.hostname, port=port, reason=str(err))]
        result.stopped = "unreachable" if str(err) == NOT_FOUND else "blocked"
        _explain(result)
        return result

    proxy = FilteringProxy(guard)
    proxy_port = await proxy.start()
    try:
        await asyncio.wait_for(_browse(url, proxy_port, proxy, result, limits), limits.hard_timeout_s)
    except TimeoutError:
        result.stopped = "timeout"
    except PlaywrightError:
        result.stopped = result.stopped or "error"
    finally:
        await proxy.stop()
        _summarize_network(result, proxy)
        _explain(result)
        result.duration_ms = int((time.monotonic() - started) * 1000)
    return result
