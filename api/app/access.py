"""Who may start a scan, and how often (safety rule 8).

Anyone may scan, limited per network address. A caller with an API key gets its own, usually
higher, limit. Keys are for scripts; the website never needs one. Only a hash of each key is
stored, so the keys themselves can't be read back from the database.

    python -m app.access create "my script" --per-hour 200
    python -m app.access list
    python -m app.access revoke 3
"""

import argparse
import hashlib
import secrets
import time

import psycopg
from fastapi import HTTPException, Request, status

from app import storage
from app.config import Settings, get_settings
from app.ratelimit import limiter

PREFIX = "ll_"
CACHE_S = 60

_known: dict[bytes, tuple[float, tuple[int, int] | None]] = {}


def new_key() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def key_hash(key: str) -> bytes:
    return hashlib.sha256(key.encode()).digest()


def client_address(request: Request, settings: Settings) -> str:
    """The caller's address. Behind a trusted proxy (a cloud host), the real address is the last
    entry the proxy added to X-Forwarded-For; without one, that header is ignored, because anyone
    can make it up."""
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


async def _lookup(database_url: str, key: str) -> tuple[int, int] | None:
    """(key id, scans per hour) for a valid key, or None."""
    digest = key_hash(key)
    hit = _known.get(digest)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=3) as conn:
        cur = await conn.execute(
            """UPDATE api_keys SET last_used_at = now() WHERE key_hash = %s AND NOT revoked
               RETURNING id, scans_per_hour""",
            (digest,),
        )
        row = await cur.fetchone()
    found = (int(row[0]), int(row[1])) if row else None
    if len(_known) > 1000:
        _known.clear()
    _known[digest] = (time.monotonic() + CACHE_S, found)
    return found


def forget() -> None:
    _known.clear()


async def allow_scan(request: Request, settings: Settings, count: int = 1) -> int:
    """Count `count` scans against the caller's limit. Returns how many are allowed (all of them or
    fewer); raises 401 for a bad key and 429 when none are allowed."""
    key = request.headers.get("x-api-key", "").strip()
    if key:
        try:
            found = await _lookup(settings.database_url, key) if key.startswith(PREFIX) else None
        except Exception as err:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "API keys can't be checked right now."
            ) from err
        if found is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That API key isn't valid.")
        bucket, limit, who = f"key:{found[0]}", found[1], "this API key"
    elif settings.require_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This scanner needs an API key (X-API-Key header).")
    else:
        bucket, limit, who = (
            client_address(request, settings),
            settings.scan_rate_limit_per_hour,
            "your network",
        )

    allowed = 0
    wait = None
    for _ in range(count):
        wait = limiter.check(bucket, limit)
        if wait is not None:
            break
        allowed += 1
    if allowed == 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many scans from {who}. Try again in {wait} minute{'s' if wait != 1 else ''}.",
        )
    return allowed


# ---------- the small command-line tool ----------


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, connect_timeout=5, autocommit=True)
    conn.execute(storage.MORE_SCHEMA)
    return conn


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage API keys for the LinkLens scan API.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="make a new key and print it once")
    create.add_argument("name")
    create.add_argument("--per-hour", type=int, default=200)
    sub.add_parser("list", help="show the keys (never the key text itself)")
    revoke = sub.add_parser("revoke", help="switch a key off")
    revoke.add_argument("id", type=int)
    args = parser.parse_args()

    with _connect() as conn:
        if args.command == "create":
            key = new_key()
            conn.execute(
                "INSERT INTO api_keys (name, key_hash, scans_per_hour) VALUES (%s, %s, %s)",
                (args.name, key_hash(key), args.per_hour),
            )
            print(f"Key for {args.name!r} ({args.per_hour} scans an hour). It is shown only this once:")
            print(key)
        elif args.command == "list":
            rows = conn.execute(
                "SELECT id, name, scans_per_hour, created_at, last_used_at, revoked FROM api_keys ORDER BY id"
            ).fetchall()
            for kid, name, per_hour, created, used, revoked in rows:
                state = "revoked" if revoked else "active"
                used = f"last used {used:%Y-%m-%d}" if used else "never used"
                print(f"{kid}  {name}  {per_hour}/hour  created {created:%Y-%m-%d}  {used}  {state}")
            if not rows:
                print("No keys yet.")
        else:
            done = conn.execute("UPDATE api_keys SET revoked = true WHERE id = %s", (args.id,)).rowcount
            print("Revoked." if done else "No key with that id.")


if __name__ == "__main__":
    main()
