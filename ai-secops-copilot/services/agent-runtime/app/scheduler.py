"""In-process scheduler / background workers (Day 18, ADR-020).

A dependency-free, asyncio-based scheduler that runs periodic maintenance jobs inside the
agent-runtime process — no Celery/Redis/cron required. It powers three operations chores:

  * **sla_sweep**        — detect SLA breaches and fire (deduped) notifications.
  * **provider_reconcile** — pull resolved tickets back into finding state (lifecycle sync).
  * **deadletter_retry** — replay decisions whose ticket action previously failed.

Jobs are plain ``async`` callables returning a small result dict; the scheduler records run
counts, timing, last status/result, and errors so the work is observable (``GET /jobs``). The
same machinery runs a job **on demand** (``POST /jobs/run/{name}``) so the behavior is fully
testable and demoable without waiting for a timer. Each run is guarded by a lock so a periodic
tick and a manual trigger never overlap, and a slow/erroring job never breaks the loop.

Designed as a pragmatic single-process worker; a multi-replica deployment would move these
behind a real broker + leader election (documented as the production follow-up in ADR-020).
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field

logger = logging.getLogger("secops.scheduler")

JobFn = Callable[[], Awaitable[dict]]


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


@dataclass
class JobState:
    name: str
    interval_s: float
    enabled: bool = True
    runs: int = 0
    errors: int = 0
    running: bool = False
    last_run: str | None = None
    last_status: str | None = None  # "ok" | "error"
    last_error: str | None = None
    last_result: dict | None = None
    last_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _Job:
    state: JobState
    fn: JobFn
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Scheduler:
    """Registers periodic async jobs and runs them on a per-job loop."""

    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False

    # -- registration -------------------------------------------------------
    def register(
        self, name: str, interval_s: float, fn: JobFn, *, enabled: bool = True
    ) -> None:
        if name in self._jobs:
            return  # idempotent: registering twice (e.g. re-entered lifespan) is a no-op
        self._jobs[name] = _Job(
            state=JobState(name=name, interval_s=interval_s, enabled=enabled), fn=fn
        )

    @property
    def names(self) -> list[str]:
        return list(self._jobs)

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> list[dict]:
        return [j.state.to_dict() for j in self._jobs.values()]

    # -- execution ----------------------------------------------------------
    async def run_job(self, name: str) -> JobState:
        """Run a single job once, now (used by the loop and the manual endpoint)."""
        job = self._jobs.get(name)
        if job is None:
            raise KeyError(name)
        async with job.lock:  # never overlap a manual run with a periodic tick
            state = job.state
            state.running = True
            started = time.perf_counter()
            try:
                result = await job.fn()
                state.last_status = "ok"
                state.last_error = None
                state.last_result = result
            except Exception as exc:  # noqa: BLE001 - a job failure must not kill the loop
                state.last_status = "error"
                state.last_error = f"{type(exc).__name__}: {exc}"
                state.errors += 1
                logger.warning("job %s failed: %s", name, state.last_error)
            finally:
                state.runs += 1
                state.running = False
                state.last_run = _now_iso()
                state.last_duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return state

    async def _loop(self, name: str) -> None:
        job = self._jobs[name]
        while self._running:
            try:
                await asyncio.sleep(job.state.interval_s)
            except asyncio.CancelledError:
                break
            if self._running and job.state.enabled:
                await self.run_job(name)

    def start(self) -> None:
        """Spawn one loop task per registered job (idempotent)."""
        if self._running:
            return
        self._running = True
        loop = asyncio.get_event_loop()
        self._tasks = [loop.create_task(self._loop(name)) for name in self._jobs]
        logger.info("scheduler started with jobs: %s", ", ".join(self._jobs) or "(none)")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks = []
        logger.info("scheduler stopped")
