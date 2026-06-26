"""MCP tool logic for the AI SecOps Copilot agent runtime.

Dependency-free of any MCP package (so it imports with the service and is testable offline),
this exposes the copilot's core operations — analyze a finding through the governed pipeline,
preview the governance gate, list/approve/reject findings, and read the audit/metrics — as
plain functions taking a :class:`TenantContext` plus arguments and returning JSON-able dicts.

The thin FastMCP wrapper in ``mcp_server.py`` registers these as MCP tools so any MCP client
(Cursor, VS Code, Antigravity, Claude Desktop) can drive the runtime. Offline-deterministic
by default (the deterministic LLM stand-in), so it works with no keys.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError

from .config import Settings
from .domain import Action
from .governance import evaluate as governance_evaluate
from .metrics import compute_metrics, project_findings
from .pipeline import run_pipeline
from .schemas import Finding


def analyze_finding(ctx: Any, retriever: Any, finding: dict) -> dict[str, Any]:
    """Run one finding through the full governed pipeline (analysis → governance → action).

    ``finding`` is a normalized SARIF/Semgrep-style record (needs at least id, ruleId, title,
    message, file). Returns the decision + the action outcome (auto-ticket / approval queue /
    escalate), and records the decision on the audit trail."""
    try:
        validated = Finding.model_validate(finding)
    except ValidationError as exc:
        return {"error": "invalid finding", "details": exc.errors()}
    started = time.perf_counter()
    out = run_pipeline(
        validated.model_dump(),
        provider=ctx.provider,
        approvals=ctx.approvals,
        escalations=ctx.escalations,
        dead_letter=ctx.dead_letter,
        retriever=retriever,
        policy=ctx.policy,
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    ctx.audit.record(
        out["decision"], out["action"]["outcome"], actor="system", latency_ms=latency_ms
    )
    return out


def governance_preview(
    settings: Settings, confidence: float, recommended_action: str = "create_ticket"
) -> dict[str, Any]:
    """Preview the two-threshold, three-disposition governance gate for a confidence score
    (no LLM call): e.g. 0.95 → auto_execute, 0.71 → human_approval, 0.40 → escalate."""
    try:
        action = Action(recommended_action)
    except ValueError:
        action = Action.CREATE_TICKET
    decision = governance_evaluate(
        confidence=confidence,
        recommended_action=action,
        auto_threshold=settings.auto_threshold,
        suggest_threshold=settings.suggest_threshold,
    )
    return {
        "confidence": confidence,
        "recommendedAction": action.value,
        "disposition": decision.disposition.value,
        "requiresHuman": decision.requires_human,
        "reason": decision.reason,
        "reasonCode": decision.reason_code.value,
    }


def list_findings(ctx: Any) -> dict[str, Any]:
    """Current-state findings (deduped by hash), each with its linked ticket + pending flag."""
    findings = project_findings(ctx.audit.list_all())
    pending = {p.findingHash for p in ctx.approvals.list_pending()}
    for f in findings:
        ticket = ctx.provider.get(f["findingHash"])
        f["ticket"] = (
            {"key": ticket.key, "provider": ticket.provider, "status": ticket.status}
            if ticket is not None else None
        )
        f["pendingApproval"] = f["findingHash"] in pending
    findings.sort(key=lambda f: f["lastUpdated"], reverse=True)
    return {"count": len(findings), "findings": findings}


def list_approvals(ctx: Any) -> dict[str, Any]:
    """Decisions awaiting human approval before a ticket is created (the HITL queue)."""
    pending = ctx.approvals.list_pending()
    return {"count": len(pending), "pending": [p.decision for p in pending]}


def approve(ctx: Any, finding_hash: str) -> dict[str, Any]:
    """Approve a queued decision → create the ticket (human-in-the-loop gate)."""
    pending = ctx.approvals.get(finding_hash)
    try:
        ticket, created = ctx.approvals.approve(finding_hash, ctx.provider)
    except KeyError:
        return {"error": f"no pending approval for {finding_hash}"}
    outcome = "ticket_created" if created else "ticket_exists"
    if pending is not None:
        ctx.audit.record(pending.decision, outcome, actor="human")
    return {"outcome": outcome, "approvedBy": "human", "ticket": ticket.to_dict()}


def reject(ctx: Any, finding_hash: str) -> dict[str, Any]:
    """Reject a queued decision (no ticket is created)."""
    pending = ctx.approvals.get(finding_hash)
    if not ctx.approvals.reject(finding_hash):
        return {"error": f"no pending approval for {finding_hash}"}
    if pending is not None:
        ctx.audit.record(pending.decision, "rejected", actor="human")
    return {"outcome": "rejected", "findingHash": finding_hash}


def audit(ctx: Any) -> dict[str, Any]:
    """The append-only governance audit trail: why each decision was taken, by whom."""
    records = ctx.audit.list_all()
    return {"count": len(records), "records": [r.to_dict() for r in records]}


def metrics(ctx: Any) -> dict[str, Any]:
    """Platform KPIs: automation rate, pending approvals, escalations, tickets, dead-letters."""
    return compute_metrics(
        ctx.audit.list_all(),
        tickets=len(ctx.provider.all()),
        pending_approvals=len(ctx.approvals.list_pending()),
        escalations=len(ctx.escalations.list_all()),
        dead_letters=len(ctx.dead_letter.list_all()),
    )


def knowledge_search(retriever: Any, query: str, k: int = 3) -> dict[str, Any]:
    """Retrieve OWASP/CWE guidance for a free-text query (the RAG knowledge layer)."""
    if retriever is None:
        return {"error": "RAG is disabled (RAG_ENABLED=false)"}
    try:
        hits = retriever.retrieve(query, k=k)
    except Exception as exc:  # noqa: BLE001 - surface backend errors cleanly
        return {"error": f"retriever error: {exc}"}
    return {
        "query": query,
        "count": len(hits),
        "results": [
            {**h.to_citation(), "type": h.document.type, "snippet": h.document.text}
            for h in hits
        ],
    }
