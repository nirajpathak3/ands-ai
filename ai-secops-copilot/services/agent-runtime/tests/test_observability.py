"""Tests for the Day-12 observability layer: tracing, time-series, alerts, Prometheus."""

from app.config import Settings
from app.gateway import Gateway, LLMRequest, Message
from app.gateway.providers import DeterministicProvider
from app.observability.alerts import default_rules, evaluate_alerts
from app.observability.prometheus import render_prometheus
from app.observability.timeseries import TimeSeries
from app.observability.tracing import Tracer

FINDING = {
    "id": "F-1", "ruleId": "r", "cwe": "CWE-89", "file": "app/x.py",
    "scannerSeverity": "ERROR",
    "codeSnippet": "cursor.execute('...' + request.args['q'])",
}


# --- tracing -----------------------------------------------------------------

def test_span_records_duration_and_nesting():
    tracer = Tracer()
    with tracer.start_span("parent", a=1) as parent:
        with tracer.start_span("child") as child:
            pass
    spans = {s["name"]: s for s in tracer.recent()}
    assert spans["parent"]["durationMs"] >= 0
    assert spans["child"]["parentId"] == parent.span_id
    assert spans["child"]["traceId"] == parent.trace_id
    assert child.parent_id == parent.span_id


def test_span_captures_error_status():
    tracer = Tracer()
    try:
        with tracer.start_span("boom"):
            raise ValueError("nope")
    except ValueError:
        pass
    span = tracer.recent()[0]
    assert span["status"] == "error"
    assert "nope" in span["attributes"]["error"]


# --- time-series -------------------------------------------------------------

def test_timeseries_records_and_buckets():
    ts = TimeSeries()
    ts.record_llm(latency_ms=10.0, cost_usd=0.001, provider="openai", cache_hit=False, tokens=50)
    ts.record_llm(latency_ms=20.0, cost_usd=0.002, provider="openai", cache_hit=True, tokens=0)
    assert len(ts.recent("llm")) == 2
    buckets = ts.buckets("llm", window_s=300, bucket_s=30)
    total = sum(b["count"] for b in buckets)
    assert total == 2
    assert any(b["costSum"] > 0 for b in buckets)


# --- alerts ------------------------------------------------------------------

def test_alerts_fire_on_breaches():
    snap = {
        "deadLetters": 2,
        "pendingApprovals": 100,
        "rates": {"escalation": 0.9},
        "latencyMs": {"p95": 9000},
        "gateway": {"fallbackRate": 0.9, "costPerRequestUsd": 1.0},
    }
    firing = {a["name"] for a in evaluate_alerts(snap, default_rules(Settings()))}
    assert "dead_letter_present" in firing
    assert "escalation_rate_high" in firing
    assert "approval_backlog_high" in firing
    assert "llm_fallback_rate_high" in firing
    assert "latency_p95_high" in firing


def test_alerts_quiet_when_healthy():
    snap = {
        "deadLetters": 0, "pendingApprovals": 1,
        "rates": {"escalation": 0.05},
        "latencyMs": {"p95": 50},
        "gateway": {"fallbackRate": 0.0, "costPerRequestUsd": 0.0},
    }
    assert evaluate_alerts(snap, default_rules(Settings())) == []


def test_critical_alerts_sort_first():
    snap = {
        "deadLetters": 1, "rates": {"escalation": 0.9},
        "pendingApprovals": 0, "latencyMs": {"p95": 0},
        "gateway": {"fallbackRate": 0.0, "costPerRequestUsd": 0.0},
    }
    firing = evaluate_alerts(snap, default_rules(Settings()))
    assert firing[0]["severity"] == "critical"


# --- prometheus --------------------------------------------------------------

def test_prometheus_exposition_format():
    snap = {
        "findingsProcessed": 6, "decisionEvents": 6, "ticketsCreated": 2,
        "pendingApprovals": 1, "escalations": 0, "deadLetters": 0,
        "rates": {"automation": 0.3, "escalation": 0.0},
        "latencyMs": {"p95": 12.0},
        "gateway": {"totalRequests": 6, "cacheHits": 0, "fallbackUsed": 0,
                    "totalCostUsd": 0.0, "totalTokens": 100, "meanLatencyMs": 0.2},
    }
    text = render_prometheus(snap, [{"name": "x", "severity": "warning"}])
    assert "# HELP secops_findings_processed" in text
    assert "# TYPE secops_llm_requests_total counter" in text
    assert "secops_findings_processed 6" in text
    assert 'secops_alert_firing{name="x",severity="warning"} 1' in text


# --- gateway integration -----------------------------------------------------

def test_gateway_observer_feeds_timeseries():
    ts = TimeSeries()
    tracer = Tracer()
    gw = Gateway(
        [DeterministicProvider()],
        observer=lambda e: ts.record_llm(**e),
        tracer=tracer,
    )
    req = LLMRequest(
        messages=[Message(role="system", content="s"), Message(role="user", content="u")],
        task="analysis", finding=FINDING,
    )
    gw.complete(req)
    assert len(ts.recent("llm")) == 1
    assert ts.recent("llm")[0]["provider"] == "deterministic"
    assert any(s["name"] == "llm.complete" for s in tracer.recent())
