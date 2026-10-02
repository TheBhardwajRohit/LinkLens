"""What LinkLens itself has seen before: earlier scans of the same domain."""

from datetime import datetime

import psycopg

from app.blacklists.models import SourceResult

ID = "linklens"
NAME = "LinkLens history"
WORDS = {"safe": "looked safe", "suspicious": "looked suspicious", "dangerous": "looked dangerous"}


def _day(t: datetime) -> str:
    return f"{t.day} {t.strftime('%b %Y')}"


async def check(database_url: str | None, domain: str | None) -> SourceResult:
    result = SourceResult(id=ID, name=NAME)
    if not database_url or not domain:
        result.status = "skipped"
        return result
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=3) as conn:
        cur = await conn.execute(
            """SELECT verdict, score, created_at FROM scans
               WHERE registered_domain = %s ORDER BY created_at DESC LIMIT 50""",
            (domain,),
        )
        rows = await cur.fetchall()
    if not rows:
        result.status = "unknown"
        result.note = "This is the first time LinkLens has scanned this domain."
        return result
    verdict, score, when = rows[0]
    bad = sum(1 for r in rows if r[0] == "dangerous")
    result.status = "info"
    result.detail = {"scans": len(rows), "dangerous": bad, "last_verdict": verdict, "last_score": score}
    times = "once" if len(rows) == 1 else f"{len(rows)} times"
    result.note = (
        f"LinkLens has scanned this domain {times} before. "
        f"Last time ({_day(when)}) it {WORDS.get(verdict, verdict)}, with a score of {score}."
    )
    return result
