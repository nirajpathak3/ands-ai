"""Alerting on governance / cost / reliability signals (Day 12, ADR-015).

A small, transparent rule engine evaluated against a metrics *snapshot* (governance KPIs +
gateway metrics + store counts). Each rule is a pure predicate, so it's trivially testable
and the firing logic is explainable — important for an autonomy-governance product where an
operator must trust why an alert fired. Thresholds come from ``Settings`` (env-overridable).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class AlertRule:
    name: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    predicate: Callable[[Mapping], bool]
    message: Callable[[Mapping], str]


def _g(snap: Mapping, *path, default=0.0):
    cur: object = snap
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur


def default_rules(settings) -> list[AlertRule]:
    esc = settings.alert_escalation_rate
    fb = settings.alert_fallback_rate
    p95 = settings.alert_p95_latency_ms
    cost = settings.alert_cost_per_request_usd
    backlog = settings.alert_approval_backlog
    return [
        AlertRule(
            "dead_letter_present", "critical",
            "Ticketing failures landed in the dead-letter queue.",
            lambda s: _g(s, "deadLetters") > 0,
            lambda s: f"{int(_g(s, 'deadLetters'))} decision(s) in the dead-letter queue.",
        ),
        AlertRule(
            "escalation_rate_high", "warning",
            f"Escalation rate exceeds {esc:.0%} (autonomy degrading / ambiguous inflow).",
            lambda s: _g(s, "rates", "escalation") > esc,
            lambda s: f"Escalation rate {_g(s, 'rates', 'escalation'):.0%} > {esc:.0%}.",
        ),
        AlertRule(
            "approval_backlog_high", "warning",
            f"Pending human approvals exceed {backlog} (review queue backing up).",
            lambda s: _g(s, "pendingApprovals") > backlog,
            lambda s: f"{int(_g(s, 'pendingApprovals'))} approvals pending (> {backlog}).",
        ),
        AlertRule(
            "llm_fallback_rate_high", "warning",
            f"Gateway fallback rate exceeds {fb:.0%} (primary provider degraded).",
            lambda s: _g(s, "gateway", "fallbackRate") > fb,
            lambda s: f"LLM fallback rate {_g(s, 'gateway', 'fallbackRate'):.0%} > {fb:.0%}.",
        ),
        AlertRule(
            "llm_cost_per_request_high", "warning",
            f"Gateway cost/request exceeds ${cost:.4f} (spend anomaly).",
            lambda s: _g(s, "gateway", "costPerRequestUsd") > cost,
            lambda s: (
                f"LLM cost/request ${_g(s, 'gateway', 'costPerRequestUsd'):.4f} > ${cost:.4f}."
            ),
        ),
        AlertRule(
            "latency_p95_high", "warning",
            f"Decision p95 latency exceeds {p95:.0f}ms.",
            lambda s: _g(s, "latencyMs", "p95") > p95,
            lambda s: f"p95 latency {_g(s, 'latencyMs', 'p95'):.0f}ms > {p95:.0f}ms.",
        ),
    ]


def evaluate_alerts(snapshot: Mapping, rules: list[AlertRule]) -> list[dict]:
    """Return the firing alerts (rule fired -> dict with severity + message)."""
    firing: list[dict] = []
    for rule in rules:
        try:
            if rule.predicate(snapshot):
                firing.append({
                    "name": rule.name,
                    "severity": rule.severity,
                    "description": rule.description,
                    "message": rule.message(snapshot),
                })
        except Exception:  # noqa: BLE001 - a bad rule must not break the endpoint
            continue
    order = {"critical": 0, "warning": 1, "info": 2}
    firing.sort(key=lambda a: order.get(a["severity"], 3))
    return firing
