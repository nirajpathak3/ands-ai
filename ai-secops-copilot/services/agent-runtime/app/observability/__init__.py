"""Observability & ops (Day 12, ADR-015).

One place for the three operational pillars, all stdlib and offline-first:

  * **traces**  - an in-process tracer (``get_tracer``) with structured JSON logs and an
                  optional OpenTelemetry export when ``OTEL_ENABLED=true``.
  * **metrics** - a rolling time-series (``get_timeseries``) for cost/latency over time,
                  plus Prometheus text exposition (``render_prometheus``).
  * **alerts**  - a transparent rule engine over a metrics snapshot (``evaluate_alerts``).

Process-wide singletons so traces/series accumulate across requests; ``reset_observability``
clears them for the demo reset and tests.
"""

from __future__ import annotations

import logging

from ..config import Settings
from .alerts import AlertRule, default_rules, evaluate_alerts
from .prometheus import render_prometheus
from .timeseries import TimeSeries
from .tracing import Tracer, build_otel_exporter

__all__ = [
    "AlertRule",
    "TimeSeries",
    "Tracer",
    "configure_logging",
    "default_rules",
    "evaluate_alerts",
    "get_timeseries",
    "get_tracer",
    "render_prometheus",
    "reset_observability",
]

_TRACER: Tracer | None = None
_TIMESERIES: TimeSeries | None = None
_LOGGING_DONE = False


class _JsonLogFormatter(logging.Formatter):
    """Compact structured log lines (key=span payload when present)."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        base = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        span = getattr(record, "span", None)
        if span is not None:
            base["span"] = span
        return json.dumps(base, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Install a JSON (or plain) handler once for the trace/app loggers."""
    global _LOGGING_DONE
    if _LOGGING_DONE:
        return
    handler = logging.StreamHandler()
    if settings.log_json:
        handler.setFormatter(_JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger("secops")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    _LOGGING_DONE = True


def get_tracer(settings: Settings | None = None) -> Tracer:
    global _TRACER
    if _TRACER is None:
        from ..config import get_settings

        settings = settings or get_settings()
        _TRACER = Tracer(otel_export=build_otel_exporter(settings))
    return _TRACER


def get_timeseries() -> TimeSeries:
    global _TIMESERIES
    if _TIMESERIES is None:
        _TIMESERIES = TimeSeries()
    return _TIMESERIES


def reset_observability(settings: Settings | None = None) -> None:
    """Clear traces + time-series (demo reset / tests)."""
    if _TRACER is not None:
        _TRACER.clear()
    if _TIMESERIES is not None:
        _TIMESERIES.clear()
