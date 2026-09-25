"""Asks the sandbox to visit a link. The API never opens target links itself."""

import httpx

# The sandbox caps a visit at 60 seconds and may queue for up to 60 more.
TIMEOUT = httpx.Timeout(130, connect=5)


class SandboxBusy(Exception):
    pass


class SandboxUnavailable(Exception):
    pass


async def visit(sandbox_url: str, url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{sandbox_url.rstrip('/')}/visit", json={"url": url})
    except httpx.HTTPError as err:
        raise SandboxUnavailable from err
    if resp.status_code == 429:
        raise SandboxBusy
    if resp.status_code != 200:
        raise SandboxUnavailable(f"sandbox returned {resp.status_code}")
    return resp.json()
