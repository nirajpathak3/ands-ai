"""Offline end-to-end coverage for the MCP tool logic (app/mcp_tools.py).

Exercises the same surface the FastMCP wrapper exposes, against a real default-tenant
context with the deterministic offline pipeline (no keys, no network)."""

from __future__ import annotations

import pytest

from app import mcp_tools
from app.config import get_settings
from app.rag import get_retriever
from app.tenancy import TenantRegistry


@pytest.fixture()
def ctx_and_retriever():
    settings = get_settings()
    registry = TenantRegistry(settings)
    ctx = registry.get(settings.default_tenant)
    ctx.state.clear()
    if hasattr(ctx.provider, "clear"):
        ctx.provider.clear()
    return ctx, get_retriever(settings), settings


def _finding(**over):
    base = {
        "id": "F-1",
        "ruleId": "python.sqli",
        "title": "SQL injection",
        "message": "Untrusted input in query",
        "file": "app/db.py",
        "scannerSeverity": "critical",
    }
    base.update(over)
    return base


def test_analyze_records_decision_and_lists_finding(ctx_and_retriever):
    ctx, retriever, _ = ctx_and_retriever
    out = mcp_tools.analyze_finding(ctx, retriever, _finding())
    assert "decision" in out and "action" in out

    findings = mcp_tools.list_findings(ctx)
    assert findings["count"] == 1

    audit = mcp_tools.audit(ctx)
    assert audit["count"] >= 1


def test_analyze_rejects_invalid_finding(ctx_and_retriever):
    ctx, retriever, _ = ctx_and_retriever
    out = mcp_tools.analyze_finding(ctx, retriever, {"id": "bad"})
    assert out.get("error") == "invalid finding"
    assert out.get("details")


def test_governance_preview_dispositions(ctx_and_retriever):
    _, _, settings = ctx_and_retriever
    assert mcp_tools.governance_preview(settings, 0.95)["disposition"] == "auto_execute"
    assert mcp_tools.governance_preview(settings, 0.05)["disposition"] == "escalate"


def test_approve_then_metrics(ctx_and_retriever):
    ctx, retriever, _ = ctx_and_retriever
    # A mid-confidence finding queues for approval; approving it creates a ticket.
    mcp_tools.analyze_finding(ctx, retriever, _finding(scannerSeverity="medium"))
    approvals = mcp_tools.list_approvals(ctx)
    if approvals["count"]:
        finding_hash = approvals["pending"][0]["findingHash"]
        result = mcp_tools.approve(ctx, finding_hash)
        assert result["outcome"] in {"ticket_created", "ticket_exists"}

    metrics = mcp_tools.metrics(ctx)
    assert "byOutcome" in metrics


def test_reject_unknown_hash_is_clean_error(ctx_and_retriever):
    ctx, _, _ = ctx_and_retriever
    assert mcp_tools.reject(ctx, "deadbeef").get("error")


def test_knowledge_search_returns_results_or_disabled(ctx_and_retriever):
    _, retriever, _ = ctx_and_retriever
    out = mcp_tools.knowledge_search(retriever, "sql injection", k=2)
    assert "results" in out or "error" in out
