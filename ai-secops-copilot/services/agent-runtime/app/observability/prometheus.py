"""Prometheus text exposition (Day 12, ADR-015).

Hand-rolled (no client library) so the runtime exports a standard ``/observability/metrics``
scrape target with zero extra dependencies. Renders the governance KPIs, gateway egress
metrics, and current alert states into the 0.0.4 text format.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_PREFIX = "secops"


def _line(name: str, value: float, labels: dict | None = None) -> str:
    if labels:
        rendered = ",".join(f'{k}="{v}"' for k, v in labels.items())
        return f"{_PREFIX}_{name}{{{rendered}}} {value}"
    return f"{_PREFIX}_{name} {value}"


def _metric(out: list[str], name: str, mtype: str, help_text: str, value, labels=None) -> None:
    out.append(f"# HELP {_PREFIX}_{name} {help_text}")
    out.append(f"# TYPE {_PREFIX}_{name} {mtype}")
    out.append(_line(name, value, labels))


def render_prometheus(snapshot: Mapping, alerts: Sequence[Mapping] = ()) -> str:
    out: list[str] = []

    def _sub(key: str) -> Mapping:
        v = snapshot.get(key)
        return v if isinstance(v, Mapping) else {}

    g = _sub("gateway")
    rates = _sub("rates")
    latency = _sub("latencyMs")

    _metric(out, "findings_processed", "gauge", "Unique findings processed.",
            int(snapshot.get("findingsProcessed", 0)))
    _metric(out, "decision_events_total", "counter", "Total governed decision events.",
            int(snapshot.get("decisionEvents", 0)))
    _metric(out, "tickets_created", "gauge", "Tickets created (idempotent).",
            int(snapshot.get("ticketsCreated", 0)))
    _metric(out, "pending_approvals", "gauge", "Decisions awaiting human approval.",
            int(snapshot.get("pendingApprovals", 0)))
    _metric(out, "escalations", "gauge", "Findings escalated to a human.",
            int(snapshot.get("escalations", 0)))
    _metric(out, "dead_letters", "gauge", "Items in the ticketing dead-letter queue.",
            int(snapshot.get("deadLetters", 0)))

    _metric(out, "automation_rate", "gauge", "Share of findings acted on without a human.",
            float(rates.get("automation", 0.0)))
    _metric(out, "escalation_rate", "gauge", "Share of findings escalated.",
            float(rates.get("escalation", 0.0)))
    _metric(out, "decision_latency_p95_ms", "gauge", "p95 decision latency (ms).",
            float(latency.get("p95", 0.0)))

    _metric(out, "llm_requests_total", "counter", "Total Gateway LLM requests.",
            int(g.get("totalRequests", 0)))
    _metric(out, "llm_cache_hits_total", "counter", "Gateway semantic-cache hits.",
            int(g.get("cacheHits", 0)))
    _metric(out, "llm_fallback_total", "counter", "Gateway fallback invocations.",
            int(g.get("fallbackUsed", 0)))
    _metric(out, "llm_cost_usd_total", "counter", "Estimated cumulative LLM spend (USD).",
            float(g.get("totalCostUsd", 0.0)))
    _metric(out, "llm_tokens_total", "counter", "Total tokens across LLM calls.",
            int(g.get("totalTokens", 0)))
    _metric(out, "llm_mean_latency_ms", "gauge", "Mean Gateway latency per served call (ms).",
            float(g.get("meanLatencyMs", 0.0)))

    # Alert states as gauges (1 = firing) so Alertmanager/Grafana can key off them.
    out.append(f"# HELP {_PREFIX}_alert_firing Whether a named alert is currently firing.")
    out.append(f"# TYPE {_PREFIX}_alert_firing gauge")
    if alerts:
        for a in alerts:
            out.append(_line("alert_firing", 1, {"name": a["name"], "severity": a["severity"]}))
    else:
        out.append(_line("alert_firing", 0, {"name": "none", "severity": "none"}))

    return "\n".join(out) + "\n"
