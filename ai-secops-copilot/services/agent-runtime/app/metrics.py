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


def project_findings(records: Sequence[AuditRecord]) -> list[dict]:
    """Collapse the append-only audit trail into current-state findings.

    Event log -> materialized view: one entry per ``findingHash`` holding the latest
    decision plus how many times it has been (re-)evaluated. This is what the dashboard
    shows so re-ingesting the same report never duplicates a finding row.
    """
    latest: dict[str, AuditRecord] = {}
    evaluations: dict[str, int] = {}
    first_seen: dict[str, str] = {}
    for r in records:
        latest[r.findingHash] = r  # last write wins -> current state
        evaluations[r.findingHash] = evaluations.get(r.findingHash, 0) + 1
        first_seen.setdefault(r.findingHash, r.timestamp)

    findings: list[dict] = []
    for h, r in latest.items():
        findings.append({
            "findingHash": h,
            "findingId": r.findingId,
            "severity": r.severity,
            "recommendedAction": r.recommendedAction,
            "confidence": r.confidence,
            "disposition": r.disposition,
            "reasonCode": r.reasonCode,
            "outcome": r.outcome,
            "lastActor": r.actor,
            "evaluations": evaluations[h],
            "firstSeen": first_seen[h],
            "lastUpdated": r.timestamp,
        })
    return findings


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
    # Current-state view (deduped by finding) drives the KPIs, so re-ingesting the
    # same report does not inflate counts; the raw event total is exposed separately.
    findings = project_findings(records)
    n = len(findings)
    base = n or 1

    by_disposition: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for f in findings:
        by_disposition[f["disposition"]] = by_disposition.get(f["disposition"], 0) + 1
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
        by_outcome[f["outcome"]] = by_outcome.get(f["outcome"], 0) + 1

    latencies = [r.latencyMs for r in records if r.actor == "system" and r.latencyMs]
    auto = by_disposition.get("auto_execute", 0)
    approval = by_disposition.get("human_approval", 0)
    escalated = by_disposition.get("escalate", 0)
    mean_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "findingsProcessed": n,
        "decisionEvents": len(records),
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
