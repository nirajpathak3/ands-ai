"""Day 16: ticket lifecycle sync, SLA timers, and remediation tracking."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.remediation import (
    SLA_HOURS,
    build_remediation,
    is_resolved,
    remediation_item,
    sla_hours,
)

client = TestClient(app)

_CRITICAL = {
    "id": "F-REM-1", "ruleId": "formatted-sql-query", "title": "SQLi",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}

_NOW = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.UTC)


def _ticket(created: dt.datetime, *, severity="critical", status="open", resolved=None):
    return {
        "key": "SEC-1", "findingId": "F-1", "findingHash": "abc",
        "severity": severity, "status": status,
        "createdAt": created.isoformat(),
        "resolvedAt": resolved.isoformat() if resolved else None,
        "provider": "mock",
    }


# --- pure unit tests --------------------------------------------------------

def test_sla_policy():
    assert sla_hours("critical") == SLA_HOURS["critical"]
    assert sla_hours("info") is None
    assert is_resolved("closed") and is_resolved("RESOLVED")
    assert not is_resolved("open")


def test_item_on_track_for_fresh_ticket():
    item = remediation_item(None, _ticket(_NOW), _NOW)
    assert item["slaStatus"] == "on_track"
    assert item["remainingHours"] == SLA_HOURS["critical"]


def test_item_breached_when_overdue():
    created = _NOW - dt.timedelta(hours=48)  # critical budget is 24h
    item = remediation_item(None, _ticket(created), _NOW)
    assert item["slaStatus"] == "breached"
    assert item["remainingHours"] < 0


def test_item_at_risk_near_due():
    created = _NOW - dt.timedelta(hours=20)  # 4h left of a 24h budget (<25%)
    item = remediation_item(None, _ticket(created), _NOW)
    assert item["slaStatus"] == "at_risk"


def test_item_resolved_reports_mttr():
    created = _NOW - dt.timedelta(hours=10)
    resolved = _NOW - dt.timedelta(hours=2)
    item = remediation_item(None, _ticket(created, status="resolved", resolved=resolved), _NOW)
    assert item["slaStatus"] == "resolved"
    assert item["mttrHours"] == 8.0
    assert item["withinSla"] is True


def test_info_severity_has_no_sla():
    item = remediation_item(None, _ticket(_NOW, severity="info"), _NOW)
    assert item["slaStatus"] == "none"


def test_build_summary_counts():
    tickets = [
        _ticket(_NOW),                                              # on_track
        _ticket(_NOW - dt.timedelta(hours=48)),                    # breached
        _ticket(_NOW - dt.timedelta(hours=10),
                status="resolved", resolved=_NOW - dt.timedelta(hours=1)),  # resolved
    ]
    for i, t in enumerate(tickets):
        t["findingHash"] = f"h{i}"
    out = build_remediation({}, tickets, now=_NOW)
    s = out["summary"]
    assert s["total"] == 3
    assert s["open"] == 2
    assert s["resolved"] == 1
    assert s["breached"] == 1
    # breached sorts first
    assert out["items"][0]["slaStatus"] == "breached"


# --- API: lifecycle sync ----------------------------------------------------

_H = {"X-Tenant-Id": "rem-api"}


def _seed_ticket() -> str:
    client.post("/demo/reset", headers=_H)
    decision = client.post("/analyze", json={"finding": _CRITICAL}, headers=_H).json()["decision"]
    return decision["findingHash"]


def test_remediation_lists_open_ticket():
    _seed_ticket()
    body = client.get("/remediation", headers=_H).json()
    assert body["summary"]["open"] >= 1
    assert any(i["slaStatus"] == "on_track" for i in body["items"])


def test_transition_resolves_and_syncs_finding():
    h = _seed_ticket()
    res = client.post(f"/tickets/{h}/transition", json={"status": "resolved"}, headers=_H).json()
    assert res["resolved"] is True
    assert res["ticket"]["status"] == "resolved"
    assert res["ticket"]["resolvedAt"]

    # finding current-state reflects resolution
    findings = client.get("/findings", headers=_H).json()["findings"]
    target = next(f for f in findings if f["findingHash"] == h)
    assert target["outcome"] == "ticket_resolved"

    # remediation view shows it resolved with an MTTR
    rem = client.get("/remediation", headers=_H).json()
    item = next(i for i in rem["items"] if i["findingHash"] == h)
    assert item["slaStatus"] == "resolved"
    assert "mttrHours" in item


def test_transition_invalid_status_400():
    h = _seed_ticket()
    res = client.post(f"/tickets/{h}/transition", json={"status": "bogus"}, headers=_H)
    assert res.status_code == 400


def test_transition_unknown_finding_404():
    client.post("/demo/reset", headers=_H)
    res = client.post("/tickets/nope/transition", json={"status": "resolved"}, headers=_H)
    assert res.status_code == 404


def test_sync_is_idempotent():
    h = _seed_ticket()
    client.post(f"/tickets/{h}/transition", json={"status": "resolved"}, headers=_H)
    # already reconciled during transition -> sync finds nothing new
    assert client.post("/remediation/sync", headers=_H).json()["reconciled"] == 0


def test_non_terminal_transition_keeps_open():
    h = _seed_ticket()
    res = client.post(f"/tickets/{h}/transition", json={"status": "in_progress"}, headers=_H).json()
    assert res["resolved"] is False
    assert res["ticket"]["resolvedAt"] is None
