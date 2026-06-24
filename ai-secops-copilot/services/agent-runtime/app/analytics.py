"""Metrics history & trend analytics / reporting (Day 20, ADR-022).

Turns the append-only audit trail (the durable source of truth) into the kind of
time-series and roll-ups a security lead actually reads: automation/approval/escalation
rates over time, suppression and policy-suppression activity, mean latency, resolution
throughput, and a period-over-period delta — plus a self-contained Markdown exec report.

All pure functions over ``AuditRecord`` (+ an optional remediation summary for MTTR/SLA),
time-injectable for reproducible tests. No new storage: trends are derived on read, so they
survive restarts wherever the audit trail is durable (SQLite/Postgres).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence

from .ticketing import AuditRecord


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _parse(ts: str) -> _dt.datetime | None:
    try:
        parsed = _dt.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=_dt.UTC) if parsed.tzinfo is None else parsed


def _bucket_label(dt: _dt.datetime, bucket: str) -> str:
    if bucket == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if bucket == "hour":
        return dt.strftime("%Y-%m-%dT%H:00")
    return dt.strftime("%Y-%m-%d")  # day (default)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _is_policy(reason_code: str | None) -> bool:
    return bool(reason_code) and str(reason_code).startswith("policy:")


def _window_records(
    records: Sequence[AuditRecord], window_days: float, now: _dt.datetime
) -> list[AuditRecord]:
    if window_days <= 0:
        return list(records)
    cutoff = now - _dt.timedelta(days=window_days)
    kept = []
    for r in records:
        dt = _parse(r.timestamp)
        if dt is None or dt >= cutoff:
            kept.append(r)
    return kept


def bucketize(
    records: Sequence[AuditRecord],
    *,
    window_days: float = 30.0,
    bucket: str = "day",
    now: _dt.datetime | None = None,
) -> list[dict]:
    """Group decision events into time buckets with per-bucket rates and throughput."""
    now = now or utcnow()
    scoped = _window_records(records, window_days, now)

    groups: dict[str, list[AuditRecord]] = {}
    for r in scoped:
        dt = _parse(r.timestamp) or now
        groups.setdefault(_bucket_label(dt, bucket), []).append(r)

    out: list[dict] = []
    for label in sorted(groups):
        rows = groups[label]
        system = [r for r in rows if r.actor == "system"]
        n = len(system)
        auto = sum(1 for r in system if r.disposition == "auto_execute")
        approval = sum(1 for r in system if r.disposition == "human_approval")
        escalate = sum(1 for r in system if r.disposition == "escalate")
        suppressed = sum(1 for r in system if r.outcome == "suppressed")
        policy = sum(1 for r in system if _is_policy(r.reasonCode))
        resolved = sum(1 for r in rows if r.outcome == "ticket_resolved")
        latencies = [r.latencyMs for r in system if r.latencyMs]
        out.append({
            "bucket": label,
            "decisions": n,
            "autoExecute": auto,
            "humanApproval": approval,
            "escalate": escalate,
            "suppressed": suppressed,
            "policySuppressions": policy,
            "resolved": resolved,
            "automationRate": _rate(auto, n),
            "approvalRate": _rate(approval, n),
            "escalationRate": _rate(escalate, n),
            "meanLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        })
    return out


def summarize(
    records: Sequence[AuditRecord],
    *,
    remediation: dict | None = None,
    window_days: float = 30.0,
    bucket: str = "day",
    now: _dt.datetime | None = None,
) -> dict:
    """Portfolio roll-up over the window + latest-vs-previous bucket deltas."""
    now = now or utcnow()
    scoped = _window_records(records, window_days, now)
    system = [r for r in scoped if r.actor == "system"]
    n = len(system)

    auto = sum(1 for r in system if r.disposition == "auto_execute")
    approval = sum(1 for r in system if r.disposition == "human_approval")
    escalate = sum(1 for r in system if r.disposition == "escalate")
    suppressed = sum(1 for r in system if r.outcome == "suppressed")
    policy = sum(1 for r in system if _is_policy(r.reasonCode))
    resolved = sum(1 for r in scoped if r.outcome == "ticket_resolved")

    by_severity: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for r in system:
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        if r.reasonCode:
            by_reason[r.reasonCode] = by_reason.get(r.reasonCode, 0) + 1
    top_reasons = sorted(by_reason.items(), key=lambda kv: kv[1], reverse=True)[:5]

    trends = bucketize(records, window_days=window_days, bucket=bucket, now=now)
    delta = _delta(trends)

    summary = {
        "windowDays": window_days,
        "bucket": bucket,
        "decisions": n,
        "rates": {
            "automation": _rate(auto, n),
            "approval": _rate(approval, n),
            "escalation": _rate(escalate, n),
            "suppression": _rate(suppressed, n),
        },
        "suppressions": suppressed,
        "policySuppressions": policy,
        "resolved": resolved,
        "bySeverity": by_severity,
        "topReasonCodes": [{"reasonCode": k, "count": v} for k, v in top_reasons],
        "deltas": delta,
    }
    if remediation is not None:
        summary["remediation"] = {
            "open": remediation.get("open", 0),
            "resolved": remediation.get("resolved", 0),
            "breached": remediation.get("breached", 0),
            "mttrHoursMean": remediation.get("mttrHoursMean", 0.0),
            "slaCompliance": remediation.get("slaCompliance", 1.0),
        }
    return summary


def _delta(trends: list[dict]) -> dict:
    """Latest bucket vs the previous one (0 when there isn't enough history)."""
    if len(trends) < 2:
        return {"automationRate": 0.0, "decisions": 0}
    latest, prev = trends[-1], trends[-2]
    return {
        "automationRate": round(latest["automationRate"] - prev["automationRate"], 4),
        "decisions": latest["decisions"] - prev["decisions"],
    }


def build_report(summary: dict, trends: list[dict]) -> str:
    """Render a self-contained Markdown executive report from the rollup + trends."""
    r = summary["rates"]
    lines = [
        "# AI Security Operations Copilot — Activity Report",
        "",
        f"_Window: last {summary['windowDays']:g} days · bucketed by {summary['bucket']}_",
        "",
        "## Headline",
        f"- **Decisions:** {summary['decisions']}",
        f"- **Automation rate:** {r['automation'] * 100:.0f}%  "
        f"(approval {r['approval'] * 100:.0f}%, escalation {r['escalation'] * 100:.0f}%)",
        f"- **Suppressions:** {summary['suppressions']} "
        f"({summary['policySuppressions']} by policy)",
        f"- **Resolved (remediated):** {summary['resolved']}",
    ]
    rem = summary.get("remediation")
    if rem:
        lines += [
            f"- **Mean time-to-remediate:** {rem['mttrHoursMean']:g}h  "
            f"(SLA compliance {rem['slaCompliance'] * 100:.0f}%, {rem['breached']} breached)",
        ]
    if summary.get("topReasonCodes"):
        lines += ["", "## Top decision reasons"]
        lines += [f"- `{x['reasonCode']}` × {x['count']}" for x in summary["topReasonCodes"]]
    if trends:
        lines += ["", "## Trend (per bucket)", "", "| Bucket | Decisions | Auto % | Resolved |",
                  "| --- | ---: | ---: | ---: |"]
        for b in trends:
            lines.append(
                f"| {b['bucket']} | {b['decisions']} | "
                f"{b['automationRate'] * 100:.0f}% | {b['resolved']} |"
            )
    return "\n".join(lines) + "\n"
