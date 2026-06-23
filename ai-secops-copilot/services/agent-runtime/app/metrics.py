"""Operational metrics aggregation for the dashboard (Day 8).

Pure functions over the audit trail + store counts so they stay trivially testable.
These are the platform KPIs from PRODUCT_VISION.md: findings processed, tickets created,
automation / approval / escalation rates, and latency. Token cost + cache-hit rate are
gateway concerns and land with the AI Gateway (Day 11).
"""

from __future__ import annotations

from collections.abc import Sequence

from .ticketing import AuditRecord


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no numpy dependency)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1))))
    return round(ordered[k], 2)


def compute_metrics(
    records: Sequence[AuditRecord],
    *,
    tickets: int = 0,
    pending_approvals: int = 0,
    escalations: int = 0,
    dead_letters: int = 0,
) -> dict:
    """Aggregate the audit trail into dashboard KPIs.

    ``records`` excludes human approve/reject follow-ups when computing rates so the
    autonomy split reflects the system's *initial* disposition per finding.
    """
    system = [r for r in records if r.actor == "system"]
    n = len(system)
    base = n or 1

    by_disposition: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    latencies: list[float] = []
    for r in system:
        by_disposition[r.disposition] = by_disposition.get(r.disposition, 0) + 1
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        by_outcome[r.outcome] = by_outcome.get(r.outcome, 0) + 1
        if r.latencyMs:
            latencies.append(r.latencyMs)

    auto = by_disposition.get("auto_execute", 0)
    approval = by_disposition.get("human_approval", 0)
    escalated = by_disposition.get("escalate", 0)
    mean_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "findingsProcessed": n,
        "ticketsCreated": tickets,
        "pendingApprovals": pending_approvals,
        "escalations": escalations,
        "deadLetters": dead_letters,
        "rates": {
            "automation": round(auto / base, 4),
            "approval": round(approval / base, 4),
            "escalation": round(escalated / base, 4),
        },
        "latencyMs": {
            "mean": mean_latency,
            "p95": _percentile(latencies, 95),
        },
        "byDisposition": by_disposition,
        "bySeverity": by_severity,
        "byOutcome": by_outcome,
    }
