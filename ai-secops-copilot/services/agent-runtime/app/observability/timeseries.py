"""Rolling time-series of operational events (Day 12, ADR-015).

Audit records are the durable event log; this is a lightweight, in-memory ring buffer of
*timed* events so the dashboard can show **cost/latency over time** and the alert engine can
reason about recent rates. Two event kinds:

  * ``llm``      - one per Gateway completion (latency, cost, provider, cache hit, tokens).
  * ``decision`` - one per governed decision (disposition, severity, latency, outcome).

``buckets()`` aggregates a window into fixed-width time buckets for charting. Stdlib only.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Event:
    ts: float
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


class TimeSeries:
    def __init__(self, *, max_events: int = 5000) -> None:
        self._events: deque[_Event] = deque(maxlen=max_events)

    # --- recording ------------------------------------------------------------

    def record_llm(
        self, *, latency_ms: float, cost_usd: float, provider: str,
        cache_hit: bool, tokens: int = 0, task: str = "analysis",
    ) -> None:
        self._events.append(_Event(time.time(), "llm", {
            "latencyMs": round(latency_ms, 3), "costUsd": round(cost_usd, 6),
            "provider": provider, "cacheHit": bool(cache_hit), "tokens": tokens, "task": task,
        }))

    def record_decision(
        self, *, disposition: str, severity: str, latency_ms: float, outcome: str,
    ) -> None:
        self._events.append(_Event(time.time(), "decision", {
            "disposition": disposition, "severity": severity,
            "latencyMs": round(latency_ms, 3), "outcome": outcome,
        }))

    # --- reads ----------------------------------------------------------------

    def recent(self, kind: str, limit: int = 60) -> list[dict]:
        items = [e.data for e in self._events if e.kind == kind]
        return items[-limit:]

    def buckets(self, kind: str, *, window_s: float = 300.0, bucket_s: float = 30.0) -> list[dict]:
        """Aggregate the last ``window_s`` seconds of ``kind`` into fixed buckets."""
        now = time.time()
        start = now - window_s
        n_buckets = max(1, int(window_s / bucket_s))
        agg: list[dict] = [
            {"t": round(start + i * bucket_s, 3), "count": 0, "latencySum": 0.0, "costSum": 0.0}
            for i in range(n_buckets)
        ]
        for e in self._events:
            if e.kind != kind or e.ts < start:
                continue
            idx = min(n_buckets - 1, int((e.ts - start) / bucket_s))
            b = agg[idx]
            b["count"] += 1
            b["latencySum"] += float(e.data.get("latencyMs", 0.0))
            b["costSum"] += float(e.data.get("costUsd", 0.0))
        for b in agg:
            c = b["count"] or 1
            b["meanLatencyMs"] = round(b["latencySum"] / c, 3) if b["count"] else 0.0
            b["costSum"] = round(b["costSum"], 6)
            del b["latencySum"]
        return agg

    def clear(self) -> None:
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)
