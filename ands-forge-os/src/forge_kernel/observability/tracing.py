"""In-process distributed tracing (ported from ai-secops-copilot, ADR-015).

A tiny, dependency-free tracer: ``start_span`` is a context manager that times a unit of
work, links it to its parent via ``contextvars`` (so nested agent/stage calls form a
tree), records it in a bounded ring buffer for the ``/observability/traces`` endpoint,
and emits one structured log line per span. When ``OTEL_ENABLED=true`` and the
OpenTelemetry SDK is installed, each span is also exported via OTLP — the same seam,
upgraded for production with no call-site changes.

Stdlib only; OpenTelemetry is imported lazily inside the bridge.
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

_current_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
_current_span: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "span_id", default=None
)

_logger = logging.getLogger("forge.trace")


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    start_ms: float
    end_ms: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentId": self.parent_id,
            "durationMs": round(self.duration_ms, 3),
            "status": self.status,
            "attributes": self.attributes,
        }


def _short_id() -> str:
    return uuid.uuid4().hex[:16]


class Tracer:
    def __init__(self, *, max_spans: int = 1024, otel_export=None) -> None:
        self._spans: deque[Span] = deque(maxlen=max_spans)
        self._otel_export = otel_export

    @contextmanager
    def start_span(self, name: str, **attributes: Any):
        trace_id = _current_trace.get() or _short_id()
        parent_id = _current_span.get()
        span = Span(
            name=name, trace_id=trace_id, span_id=_short_id(), parent_id=parent_id,
            start_ms=time.perf_counter() * 1000, attributes=dict(attributes),
        )
        t_token = _current_trace.set(trace_id)
        s_token = _current_span.set(span.span_id)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - record failure, then re-raise
            span.status = "error"
            span.attributes["error"] = str(exc)
            raise
        finally:
            span.end_ms = time.perf_counter() * 1000
            span.duration_ms = span.end_ms - span.start_ms
            self._spans.append(span)
            _current_span.reset(s_token)
            _current_trace.reset(t_token)
            self._emit(span)

    def _emit(self, span: Span) -> None:
        _logger.info(
            "span %s (%.2fms) status=%s", span.name, span.duration_ms, span.status,
            extra={"span": span.to_dict()},
        )
        if self._otel_export is not None:
            try:
                self._otel_export(span)
            except Exception:  # noqa: BLE001 - never let export break the request path
                pass

    def recent(self, limit: int = 50) -> list[dict]:
        spans = list(self._spans)[-limit:]
        return [s.to_dict() for s in reversed(spans)]

    def clear(self) -> None:
        self._spans.clear()


def build_otel_exporter(settings) -> Any | None:
    """Return a callable(span) that exports to OpenTelemetry, or None if unavailable."""
    if not getattr(settings, "otel_enabled", False):
        return None
    try:  # pragma: no cover - exercised only when the OTel SDK is installed
        from opentelemetry import trace as _otel_trace

        tracer = _otel_trace.get_tracer("forge.kernel")

        def _export(span: Span) -> None:
            otel_span = tracer.start_span(span.name)
            for key, value in span.attributes.items():
                otel_span.set_attribute(key, value)
            otel_span.end()

        return _export
    except Exception:  # noqa: BLE001 - SDK missing/misconfigured -> in-process only
        return None
