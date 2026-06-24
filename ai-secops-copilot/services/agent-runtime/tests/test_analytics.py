"""Day 20: metrics history & trend analytics / reporting."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.analytics import bucketize, build_report, summarize
from app.main import app
from app.ticketing import AuditRecord

client = TestClient(app)


def _rec(ts, disposition="auto_execute", outcome="ticket_created", *,
         actor="system", severity="high", reason="auto_high_confidence", latency=10.0):
    return AuditRecord(
        timestamp=ts, findingHash="h" + ts, findingId="F", severity=severity,
        recommendedAction="create_ticket", confidence=0.95, disposition=disposition,
        reasonCode=reason, outcome=outcome, actor=actor, latencyMs=latency,
    )


_NOW = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


# --- bucketize --------------------------------------------------------------

def test_bucketize_groups_by_day():
    records = [
        _rec("2026-01-08T10:00:00+00:00"),
        _rec("2026-01-08T11:00:00+00:00", disposition="escalate", outcome="escalated"),
        _rec("2026-01-09T09:00:00+00:00", disposition="human_approval",
             outcome="pending_approval"),
    ]
    buckets = bucketize(records, window_days=30, bucket="day", now=_NOW)
    assert [b["bucket"] for b in buckets] == ["2026-01-08", "2026-01-09"]
    day1 = buckets[0]
    assert day1["decisions"] == 2
    assert day1["autoExecute"] == 1 and day1["escalate"] == 1
    assert day1["automationRate"] == 0.5


def test_bucketize_window_excludes_old():
    records = [_rec("2025-01-01T00:00:00+00:00"), _rec("2026-01-09T00:00:00+00:00")]
    buckets = bucketize(records, window_days=30, bucket="day", now=_NOW)
    assert [b["bucket"] for b in buckets] == ["2026-01-09"]


def test_bucketize_counts_policy_and_resolved():
    records = [
        _rec("2026-01-09T01:00:00+00:00", outcome="suppressed", reason="policy:sup"),
        _rec("2026-01-09T02:00:00+00:00", outcome="ticket_resolved", actor="provider"),
    ]
    b = bucketize(records, window_days=30, bucket="day", now=_NOW)[0]
    assert b["suppressed"] == 1
    assert b["policySuppressions"] == 1
    assert b["resolved"] == 1


# --- summarize --------------------------------------------------------------

def test_summarize_rates_and_deltas():
    records = [
        _rec("2026-01-08T10:00:00+00:00"),
        _rec("2026-01-09T10:00:00+00:00"),
        _rec("2026-01-09T11:00:00+00:00", disposition="escalate", outcome="escalated"),
    ]
    s = summarize(records, window_days=30, bucket="day", now=_NOW)
    assert s["decisions"] == 3
    assert s["rates"]["automation"] == round(2 / 3, 4)
    # latest bucket (2 decisions, 50% auto) vs previous (1 decision, 100% auto)
    assert s["deltas"]["decisions"] == 1
    assert s["deltas"]["automationRate"] == round(0.5 - 1.0, 4)


def test_summarize_includes_remediation():
    s = summarize(
        [_rec("2026-01-09T10:00:00+00:00")],
        remediation={"open": 2, "resolved": 1, "breached": 0,
                     "mttrHoursMean": 5.0, "slaCompliance": 1.0},
        now=_NOW,
    )
    assert s["remediation"]["mttrHoursMean"] == 5.0


def test_summarize_empty():
    s = summarize([], now=_NOW)
    assert s["decisions"] == 0
    assert s["rates"]["automation"] == 0.0


# --- report -----------------------------------------------------------------

def test_build_report_markdown():
    records = [_rec("2026-01-09T10:00:00+00:00")]
    s = summarize(records, now=_NOW)
    trends = bucketize(records, now=_NOW)
    report = build_report(s, trends)
    assert report.startswith("# AI Security Operations Copilot")
    assert "Automation rate" in report
    assert "| Bucket |" in report


# --- API --------------------------------------------------------------------

_H = {"X-Tenant-Id": "analytics-api"}


def test_analytics_endpoints():
    client.post("/demo/reset", headers=_H)
    client.post("/demo/seed", headers=_H)

    summary = client.get("/analytics/summary", headers=_H).json()
    assert summary["decisions"] >= 1
    assert "automation" in summary["rates"]
    assert "remediation" in summary

    trends = client.get("/analytics/trends", headers=_H).json()
    assert isinstance(trends["buckets"], list)
    assert trends["buckets"]

    report = client.get("/analytics/report", headers=_H)
    assert report.status_code == 200
    assert "AI Security Operations Copilot" in report.text
