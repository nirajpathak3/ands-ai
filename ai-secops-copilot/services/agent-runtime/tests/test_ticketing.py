"""Tests for the mock ticketing + approval layer (pure stdlib)."""

from app.ticketing import (
    ApprovalStore,
    EscalationQueue,
    MockTicketProvider,
    execute_decision,
)


def _decision(disposition, action="create_ticket", finding_hash="h1", finding_id="F-1"):
    return {
        "findingId": finding_id,
        "findingHash": finding_hash,
        "analysis": {"severity": "critical", "recommendedAction": action},
        "disposition": disposition,
        "requiresHuman": disposition != "auto_execute",
        "governanceReason": "test",
    }


def _stores():
    return MockTicketProvider(), ApprovalStore(), EscalationQueue()


def _exec(decision, provider, approvals, esc):
    return execute_decision(decision, provider=provider, approvals=approvals, escalations=esc)


def test_provider_is_idempotent_by_finding_hash():
    provider = MockTicketProvider()
    t1, created1 = provider.create(_decision("auto_execute"), via="auto")
    t2, created2 = provider.create(_decision("auto_execute"), via="auto")
    assert created1 is True and created2 is False
    assert t1.key == t2.key
    assert len(provider.all()) == 1


def test_auto_execute_creates_then_dedupes():
    provider, approvals, esc = _stores()
    r1 = _exec(_decision("auto_execute"), provider, approvals, esc)
    r2 = _exec(_decision("auto_execute"), provider, approvals, esc)
    assert r1.outcome == "ticket_created"
    assert r2.outcome == "ticket_exists"
    assert len(provider.all()) == 1


def test_auto_execute_suppress_creates_no_ticket():
    provider, approvals, esc = _stores()
    r = execute_decision(
        _decision("auto_execute", action="suppress"),
        provider=provider, approvals=approvals, escalations=esc,
    )
    assert r.outcome == "suppressed"
    assert len(provider.all()) == 0


def test_human_approval_queues_then_approves():
    provider, approvals, esc = _stores()
    r = _exec(_decision("human_approval"), provider, approvals, esc)
    assert r.outcome == "pending_approval"
    assert len(approvals.list_pending()) == 1

    ticket, created = approvals.approve("h1", provider)
    assert created is True
    assert ticket.createdVia == "approval"
    assert len(approvals.list_pending()) == 0
    assert len(provider.all()) == 1


def test_escalate_routes_to_queue():
    provider, approvals, esc = _stores()
    r = execute_decision(
        _decision("escalate", action="escalate"),
        provider=provider, approvals=approvals, escalations=esc,
    )
    assert r.outcome == "escalated"
    assert len(esc.list_all()) == 1
    assert len(provider.all()) == 0
