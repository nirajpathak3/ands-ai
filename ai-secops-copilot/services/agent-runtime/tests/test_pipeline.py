"""End-to-end walking-skeleton tests (require pydantic; run after `pip install -e .[dev]`).

Covers the Day-2 acceptance flow: Finding -> analysis (validated) -> governance ->
action, plus idempotency, the HITL approval path, and the invalid-output -> escalate
failure path with a bounded re-prompt.
"""

import json

from app.pipeline import run_pipeline
from app.ticketing import ApprovalStore, EscalationQueue, MockTicketProvider

CRITICAL_FINDING = {
    "id": "F-001", "scanner": "semgrep", "ruleId": "formatted-sql-query",
    "title": "SQL Injection", "message": "user input in SQL",
    "file": "app/api/users.py", "startLine": 42, "cwe": "CWE-89",
    "scannerSeverity": "ERROR",
    "codeSnippet": "query = '...' + request.args['name']; cursor.execute(query)",
}

MEDIUM_FINDING = {
    "id": "F-023", "scanner": "semgrep", "ruleId": "cleartext-transmission",
    "title": "Cleartext HTTP", "message": "http used", "file": "app/clients/partner.py",
    "startLine": 7, "cwe": "CWE-319", "scannerSeverity": "WARNING",
    "codeSnippet": "PARTNER_API = 'http://partner.example.com/api/v1'",
}


def _stores():
    return MockTicketProvider(), ApprovalStore(), EscalationQueue()


def test_critical_finding_auto_creates_ticket():
    provider, approvals, esc = _stores()
    out = run_pipeline(CRITICAL_FINDING, provider=provider, approvals=approvals, escalations=esc)
    assert out["decision"]["disposition"] == "auto_execute"
    assert out["action"]["outcome"] == "ticket_created"
    assert out["action"]["ticket"]["severity"] == "critical"


def test_pipeline_is_idempotent():
    provider, approvals, esc = _stores()
    run_pipeline(CRITICAL_FINDING, provider=provider, approvals=approvals, escalations=esc)
    second = run_pipeline(CRITICAL_FINDING, provider=provider, approvals=approvals, escalations=esc)
    assert second["action"]["outcome"] == "ticket_exists"
    assert len(provider.all()) == 1


def test_medium_finding_requires_approval_then_tickets():
    provider, approvals, esc = _stores()
    out = run_pipeline(MEDIUM_FINDING, provider=provider, approvals=approvals, escalations=esc)
    assert out["decision"]["disposition"] == "human_approval"
    assert out["action"]["outcome"] == "pending_approval"
    assert len(provider.all()) == 0

    finding_hash = out["decision"]["findingHash"]
    ticket, created = approvals.approve(finding_hash, provider)
    assert created is True
    assert len(provider.all()) == 1


class _BadLLM:
    """Returns non-JSON every time to exercise the validation/escalation path."""

    name = "bad"

    def analyze(self, finding):
        return "not-json-at-all"


class _RecoveringLLM:
    """Returns garbage once, then valid output (bounded re-prompt success)."""

    name = "recovering"

    def __init__(self):
        self.calls = 0

    def analyze(self, finding):
        self.calls += 1
        if self.calls == 1:
            return "{ broken json"
        return json.dumps({
            "severity": "critical", "confidence": 0.95,
            "reason": "valid on retry", "recommendedAction": "create_ticket",
        })


def test_invalid_output_escalates_after_retries():
    provider, approvals, esc = _stores()
    out = run_pipeline(
        CRITICAL_FINDING, provider=provider, approvals=approvals, escalations=esc,
        client=_BadLLM(),
    )
    assert out["decision"]["analysis"]["recommendedAction"] == "escalate"
    assert out["action"]["outcome"] == "escalated"
    assert out["errors"]
    assert len(esc.list_all()) == 1


def test_bounded_reprompt_recovers():
    provider, approvals, esc = _stores()
    client = _RecoveringLLM()
    out = run_pipeline(
        CRITICAL_FINDING, provider=provider, approvals=approvals, escalations=esc,
        client=client,
    )
    assert client.calls == 2
    assert out["retries"] == 2
    assert out["action"]["outcome"] == "ticket_created"
