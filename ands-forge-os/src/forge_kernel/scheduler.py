"""Parallel scheduler + cost/time budget governor (PRODUCT_VISION §8 — the net-new piece).

LangGraph handles a single agent's graph; the kernel's net-new orchestration is running
**all ready artifacts of a stage concurrently** (topological waves over the intra-stage
DAG), bounded by a concurrency limit and a **budget governor** that pauses the run before
a wave would blow the cost or wall-clock cap. This is what turns the lifecycle's parallel
groups (e.g. the 3 Discovery agents) into actual concurrent execution.

Pure orchestration over a caller-supplied ``execute_fn(spec) -> AgentResult`` — it knows
nothing about agents, so it is reusable and unit-testable in isolation.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .blueprint import ArtifactSpec


class BudgetExceededError(RuntimeError):
    """The run would exceed its cost or wall-clock budget; the governor paused it."""


@dataclass
class Budget:
    """The governor's running ledger for one run."""

    max_usd: float
    max_wall_seconds: float
    spent_usd: float = 0.0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at

    def check(self, *, about_to_spend: float = 0.0) -> None:
        if self.spent_usd + about_to_spend > self.max_usd:
            raise BudgetExceededError(
                f"cost budget exceeded: spent ${self.spent_usd:.4f} + "
                f"${about_to_spend:.4f} > cap ${self.max_usd:.4f}"
            )
        if self.elapsed_seconds > self.max_wall_seconds:
            raise BudgetExceededError(
                f"wall-clock budget exceeded: {self.elapsed_seconds:.1f}s > "
                f"cap {self.max_wall_seconds:.1f}s"
            )

    def charge(self, usd: float) -> None:
        self.spent_usd = round(self.spent_usd + usd, 6)


def topological_waves(artifacts: Sequence[ArtifactSpec]) -> list[list[ArtifactSpec]]:
    """Group a stage's artifacts into parallel waves honoring intra-stage ``depends_on``.

    Edges to artifacts outside this set (e.g. a previous stage) are ignored — those are
    already satisfied by the time the stage runs. Wave 0 is everything with no in-set
    dependency (the fan-out); later waves unlock as predecessors complete. Raises on a
    cycle (the blueprint validator should have caught it first).
    """
    in_set = {a.key for a in artifacts}
    pending = {a.key: {d for d in a.depends_on if d in in_set} for a in artifacts}
    by_key = {a.key: a for a in artifacts}
    waves: list[list[ArtifactSpec]] = []
    done: set[str] = set()

    while pending:
        ready = [k for k, deps in pending.items() if deps <= done]
        if not ready:
            raise BudgetExceededError(  # pragma: no cover - guarded by validate()
                f"unschedulable artifacts (cycle?): {sorted(pending)}"
            )
        ready.sort()  # deterministic ordering within a wave
        waves.append([by_key[k] for k in ready])
        done.update(ready)
        for k in ready:
            pending.pop(k)
    return waves


@dataclass
class StageRun:
    """What the scheduler produced for one stage (for audit + parallelism evidence)."""

    results: dict[str, Any]  # artifact key -> AgentResult
    waves: list[list[str]]  # artifact keys per parallel wave
    max_parallelism: int
    duration_ms: float


class ParallelScheduler:
    def __init__(self, *, max_concurrency: int = 4, tracer: Any = None) -> None:
        self._max_concurrency = max(1, max_concurrency)
        self._tracer = tracer

    def run_stage(
        self,
        stage_key: str,
        artifacts: Sequence[ArtifactSpec],
        execute_fn: Callable[[ArtifactSpec], Any],
        *,
        budget: Budget,
    ) -> StageRun:
        """Run a stage's artifacts in topological parallel waves under the budget."""
        start = time.perf_counter()
        waves = topological_waves(artifacts)
        results: dict[str, Any] = {}
        wave_keys: list[list[str]] = []
        max_parallel = 1

        span_cm = (
            self._tracer.start_span("scheduler.stage", stage=stage_key)
            if self._tracer is not None else _null()
        )
        with span_cm:
            for wave in waves:
                budget.check()  # governor checkpoint before each wave
                workers = min(self._max_concurrency, len(wave))
                max_parallel = max(max_parallel, workers)
                if workers == 1:
                    spec = wave[0]
                    results[spec.key] = execute_fn(spec)
                else:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        futures = {pool.submit(execute_fn, s): s for s in wave}
                        for fut in futures:
                            spec = futures[fut]
                            results[spec.key] = fut.result()
                wave_keys.append([s.key for s in wave])

        return StageRun(
            results=results,
            waves=wave_keys,
            max_parallelism=max_parallel,
            duration_ms=round((time.perf_counter() - start) * 1000, 3),
        )


class _null:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False
