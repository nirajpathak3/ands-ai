"""Remediation tracking & SLA timers (Day 16, ADR-018).

Once a finding becomes a ticket, the platform tracks it to closure. This module is the
pure-function core: it holds the **SLA policy** (time-to-remediate budget per severity),
the canonical **ticket statuses**, and the projection that joins findings + tickets into a
**remediation view** with per-item SLA status (on-track / at-risk / breached / resolved)
and a portfolio **summary** (open vs resolved, SLA compliance, mean time-to-remediate).

Kept dependency-free and time-injectable so it is trivially testable and reproducible.
"""

from __future__ import annotations

import datetime as _dt

# Canonical ticket lifecycle. A ticket starts ``open`` and is resolved when an external
# system (Jira/ServiceNow) or a human closes it — the inbound half of lifecycle sync.
RESOLVED_STATUSES = frozenset({"resolved", "closed", "done"})
VALID_STATUSES = frozenset({"open", "in_progress", "resolved", "closed", "done"})

# Time-to-remediate budget by severity (hours). ``info`` has no SLA.
SLA_HOURS: dict[str, float] = {
    "critical": 24.0,
    "high": 72.0,
    "medium": 168.0,   # 7 days
    "low": 720.0,      # 30 days
}

# Fraction of the SLA budget remaining below which an open item is "at risk".
_AT_RISK_FRACTION = 0.25


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def is_resolved(status: str) -> bool:
    return (status or "").strip().lower() in RESOLVED_STATUSES


def sla_hours(severity: str) -> float | None:
    return SLA_HOURS.get((severity or "").strip().lower())


def _parse(ts: str | None) -> _dt.datetime | None:
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.UTC)
    return parsed


def _hours_between(start: _dt.datetime, end: _dt.datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def remediation_item(
    finding: dict | None, ticket: dict, now: _dt.datetime
) -> dict:
    """Join one ticket (+ its finding) into a remediation row with SLA state."""
    finding = finding or {}
    severity = ticket.get("severity") or finding.get("severity") or "unknown"
    created = _parse(ticket.get("createdAt")) or now
    resolved_at = _parse(ticket.get("resolvedAt"))
    status = str(ticket.get("status", "open"))
    budget = sla_hours(severity)

    item: dict = {
        "findingHash": ticket.get("findingHash"),
        "findingId": ticket.get("findingId") or finding.get("findingId"),
        "severity": severity,
        "ticketKey": ticket.get("key"),
        "provider": ticket.get("provider"),
        "status": status,
        "createdAt": ticket.get("createdAt"),
        "slaHours": budget,
        "ageHours": round(_hours_between(created, now), 2),
    }

    if is_resolved(status) and resolved_at is not None:
        mttr = round(_hours_between(created, resolved_at), 2)
        item.update(
            slaStatus="resolved",
            resolvedAt=ticket.get("resolvedAt"),
            mttrHours=mttr,
            withinSla=(budget is None or mttr <= budget),
        )
        return item

    if budget is None:
        item.update(slaStatus="none", dueAt=None, remainingHours=None)
        return item

    due = created + _dt.timedelta(hours=budget)
    remaining = round(_hours_between(now, due), 2)
    if remaining < 0:
        sla_status = "breached"
    elif remaining <= budget * _AT_RISK_FRACTION:
        sla_status = "at_risk"
    else:
        sla_status = "on_track"
    item.update(slaStatus=sla_status, dueAt=due.isoformat(), remainingHours=remaining)
    return item


_ORDER = {"breached": 0, "at_risk": 1, "on_track": 2, "none": 3, "resolved": 4}


def build_remediation(
    findings_by_hash: dict[str, dict],
    tickets: list[dict],
    *,
    now: _dt.datetime | None = None,
) -> dict:
    """Build the remediation view (items + portfolio summary) from tickets + findings."""
    now = now or utcnow()
    items = [
        remediation_item(findings_by_hash.get(t.get("findingHash", "")), t, now)
        for t in tickets
    ]
    items.sort(key=lambda i: (_ORDER.get(i["slaStatus"], 9), -(i.get("ageHours") or 0)))

    resolved = [i for i in items if i["slaStatus"] == "resolved"]
    open_items = [i for i in items if i["slaStatus"] != "resolved"]
    breached = [i for i in open_items if i["slaStatus"] == "breached"]
    at_risk = [i for i in open_items if i["slaStatus"] == "at_risk"]
    mttrs = [i["mttrHours"] for i in resolved if "mttrHours" in i]
    within = [i for i in resolved if i.get("withinSla")]

    total = len(items)
    summary = {
        "total": total,
        "open": len(open_items),
        "resolved": len(resolved),
        "breached": len(breached),
        "atRisk": len(at_risk),
        "onTrack": len([i for i in open_items if i["slaStatus"] == "on_track"]),
        "mttrHoursMean": round(sum(mttrs) / len(mttrs), 2) if mttrs else 0.0,
        # Compliance over resolved items: fraction closed within their SLA budget.
        "slaCompliance": round(len(within) / len(resolved), 4) if resolved else 1.0,
    }
    return {"summary": summary, "items": items}
