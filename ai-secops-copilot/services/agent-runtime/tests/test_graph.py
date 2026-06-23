"""Tests for the compiled LangGraph agent (Day 9): routing, interrupt + resume.

Skipped automatically if LangGraph isn't installed (the inline pipeline is the
dependency-free fallback and is covered by test_pipeline.py).
"""

import json

import pytest

pytest.importorskip("langgraph")

from app.graph import GraphRunner  # noqa: E402
from app.ticketing import ApprovalStore, EscalationQueue, MockTicketProvider  # noqa: E402

CRITICAL = {
    "id": "F-G1", "scanner": "semgrep", "ruleId": "formatted-sql-query",
    "title": "SQLi", "message": "user input in SQL", "file": "app/api/users.py",
    "startLine": 42, "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}
MEDIUM = {
    "id": "F-G2", "scanner": "semgrep", "ruleId": "cleartext-transmission",
    "title": "Cleartext HTTP", "message": "http used", "file": "app/clients/p.py",
    "startLine": 7, "cwe": "CWE-319", "scannerSeverity": "WARNING",
    "codeSnippet": "PARTNER_API = 'http://partner.example.com/api/v1'",
}


def _runner():
    return GraphRunner(
        provider=MockTicketProvider(), approvals=ApprovalStore(), escalations=EscalationQueue()
    )


def test_graph_has_conditional_action_nodes():
    nodes = _runner().nodes()
    for name in ("ingest", "finding_analysis", "ticket_decision", "execute", "await_approval"):
        assert name in nodes


def test_critical_auto_executes_through_graph():
    out = _runner().analyze(CRITICAL)
    assert out["status"] == "completed"
    assert out["decision"]["disposition"] == "auto_execute"
    assert out["action"]["outcome"] == "ticket_created"


def test_medium_interrupts_then_resume_approves():
    runner = _runner()
    out = runner.analyze(MEDIUM)
    assert out["status"] == "awaiting_approval"
    assert out["interrupt"]["type"] == "approval_required"
    thread_id = out["threadId"]

    resumed = runner.resume(thread_id, approved=True)
    assert resumed["status"] == "completed"
    assert resumed["action"]["outcome"] == "ticket_created"


def test_medium_interrupt_then_resume_rejects():
    runner = _runner()
    thread_id = runner.analyze(MEDIUM)["threadId"]
    resumed = runner.resume(thread_id, approved=False)
    assert resumed["action"]["outcome"] == "rejected"


def test_resume_unknown_thread_raises():
    with pytest.raises(KeyError):
        _runner().resume("does-not-exist", approved=True)


class _BadLLM:
    name = "bad"

    def analyze(self, finding):
        return "not-json"


def test_invalid_output_escalates_through_graph():
    out = _runner().analyze(CRITICAL, client=_BadLLM())
    assert out["status"] == "completed"
    assert out["decision"]["analysis"]["recommendedAction"] == "escalate"
    assert out["action"]["outcome"] == "escalated"


def test_mermaid_renders_nodes():
    mermaid = _runner().mermaid()
    assert "await_approval" in mermaid and "execute" in mermaid


class _RecoveringLLM:
    name = "recovering"

    def __init__(self):
        self.calls = 0

    def analyze(self, finding):
        self.calls += 1
        if self.calls == 1:
            return "{ broken"
        return json.dumps({
            "severity": "critical", "confidence": 0.95,
            "reason": "valid on retry", "recommendedAction": "create_ticket",
        })


def test_bounded_reprompt_recovers_through_graph():
    out = _runner().analyze(CRITICAL, client=_RecoveringLLM())
    assert out["status"] == "completed"
    assert out["action"]["outcome"] == "ticket_created"
    assert out["retries"] == 2
