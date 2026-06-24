"""Per-tenant rate limiting (Day 15, ADR-017).

A small, dependency-free fixed-window limiter: each key (tenant) gets ``rpm`` requests
per rolling 60-second window. Returns the seconds until the window resets so callers can
set a ``Retry-After`` header. The limit is read per ``check`` call so it can be toggled
by configuration (and in tests) without rebuilding the limiter. ``rpm <= 0`` disables it.

In-process and per-replica by design — sufficient for a single runtime and for demos; a
distributed deployment would back this with Redis (the same ``check`` seam).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

_WINDOW_S = 60.0


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_s: float


class RateLimiter:
    """Fixed-window request counter keyed by an arbitrary string (the tenant id)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, rpm: int, *, now: float | None = None) -> RateLimitResult:
        if rpm <= 0:
            return RateLimitResult(allowed=True, remaining=-1, retry_after_s=0.0)
        now = time.monotonic() if now is None else now
        cutoff = now - _WINDOW_S
        with self._lock:
            window = self._hits.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= rpm:
                retry_after = window[0] + _WINDOW_S - now
                return RateLimitResult(
                    allowed=False, remaining=0, retry_after_s=max(0.0, retry_after)
                )
            window.append(now)
            return RateLimitResult(
                allowed=True, remaining=rpm - len(window), retry_after_s=0.0
            )

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


_LIMITER = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Process-wide rate limiter (shared across requests)."""
    return _LIMITER
