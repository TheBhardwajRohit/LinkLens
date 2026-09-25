"""Running scans, kept in memory so the page can follow their progress (Server-Sent Events).
Finished jobs stay for a few minutes, so a slow browser can still pick up the result."""

import asyncio
import json
import time
from typing import Any

KEEP_S = 15 * 60
MAX_JOBS = 200
HEARTBEAT_S = 15


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.created = time.monotonic()
        self.events: list[dict[str, Any]] = []
        self.finished = False
        self.result: dict | None = None
        self._cond = asyncio.Condition()
        self.task: asyncio.Task | None = None

    async def push(self, kind: str, data: Any, final: bool = False) -> None:
        async with self._cond:
            self.events.append({"type": kind, "data": data})
            if final:
                self.finished = True
            self._cond.notify_all()

    async def wait_beyond(self, index: int) -> tuple[list[dict], bool]:
        async with self._cond:
            await self._cond.wait_for(lambda: len(self.events) > index or self.finished)
            return self.events[index:], self.finished

    async def stream(self):
        """Every event so far, then new ones as they come, as SSE text. Ends after the last event."""
        yield "retry: 3000\n\n"
        index = 0
        while True:
            try:
                new, finished = await asyncio.wait_for(self.wait_beyond(index), HEARTBEAT_S)
            except TimeoutError:
                yield ": still working\n\n"  # keeps the connection open
                continue
            for event in new:
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                index += 1
            if finished and index >= len(self.events):
                return


_jobs: dict[str, Job] = {}


def _cleanup() -> None:
    now = time.monotonic()
    for job_id in [j for j, job in _jobs.items() if job.finished and now - job.created > KEEP_S]:
        _jobs.pop(job_id, None)
    while len(_jobs) >= MAX_JOBS:
        _jobs.pop(next(iter(_jobs)))


def create(job_id: str) -> Job:
    _cleanup()
    job = Job(job_id)
    _jobs[job_id] = job
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)
