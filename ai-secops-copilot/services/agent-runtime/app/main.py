"""FastAPI entrypoint for the agent runtime.

Day-2 walking skeleton (all runnable offline with the deterministic LLM stand-in):
  * GET  /health                         - liveness + config snapshot
  * POST /governance/preview             - confidence -> disposition (no LLM)
  * POST /analyze                        - full pipeline: Finding -> analysis ->
                                           governance -> action (auto-ticket /
                                           approval queue / escalate)
  * GET  /approvals                      - list decisions awaiting human approval
  * POST /approvals/{finding_hash}/approve - approve -> create the ticket (HITL)
  * POST /approvals/{finding_hash}/reject  - reject a pending decision
  * GET  /tickets                        - list (mock) tickets created so far
  * GET  /escalations                    - list escalated findings

Run locally:
    uvicorn app.main:app --reload --port 8088
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .config import get_settings
from .domain import Action
from .governance import evaluate as governance_evaluate
from .pipeline import run_pipeline
from .schemas import AnalyzeRequest
from .ticketing import ApprovalStore, EscalationQueue, MockTicketProvider

app = FastAPI(
    title="AI Security Operations Copilot - Agent Runtime",
    version=__version__,
    summary="LangGraph agent runtime: Finding Analysis -> Ticket Decision -> Governance Gate.",
)

# In-memory stores for the walking skeleton. Day 3 swaps the provider for a real
# Jira adapter (+ ServiceNow mock); Day 10 persists approvals via checkpointing.
_provider = MockTicketProvider()
_approvals = ApprovalStore()
_escalations = EscalationQueue()


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
        "governance": {
            "autoThreshold": settings.auto_threshold,
            "suggestThreshold": settings.suggest_threshold,
        },
    }


class GovernancePreviewRequest(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    recommendedAction: Action = Action.CREATE_TICKET


@app.post("/governance/preview")
def governance_preview(req: GovernancePreviewRequest) -> dict:
    """Demoable: the two-threshold, three-disposition gate.

    e.g. confidence 0.95 -> auto_execute; 0.71 -> human_approval; 0.40 -> escalate.
    """
    settings = get_settings()
    decision = governance_evaluate(
        confidence=req.confidence,
        recommended_action=req.recommendedAction,
        auto_threshold=settings.auto_threshold,
        suggest_threshold=settings.suggest_threshold,
    )
    return {
        "confidence": req.confidence,
        "recommendedAction": req.recommendedAction.value,
        "disposition": decision.disposition.value,
        "requiresHuman": decision.requires_human,
        "reason": decision.reason,
    }


@app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    """Run a finding through the full walking skeleton and execute the decision."""
    return run_pipeline(
        req.finding.model_dump(),
        provider=_provider,
        approvals=_approvals,
        escalations=_escalations,
    )


@app.get("/approvals")
def list_approvals() -> dict:
    pending = _approvals.list_pending()
    return {"count": len(pending), "pending": [p.decision for p in pending]}


@app.post("/approvals/{finding_hash}/approve")
def approve(finding_hash: str) -> dict:
    """Human approves a queued decision -> the ticket is created (HITL gate)."""
    try:
        ticket, created = _approvals.approve(finding_hash, _provider)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No pending approval for {finding_hash}"
        ) from None
    return {
        "outcome": "ticket_created" if created else "ticket_exists",
        "approvedBy": "human",
        "ticket": ticket.to_dict(),
    }


@app.post("/approvals/{finding_hash}/reject")
def reject(finding_hash: str) -> dict:
    if not _approvals.reject(finding_hash):
        raise HTTPException(status_code=404, detail=f"No pending approval for {finding_hash}")
    return {"outcome": "rejected", "findingHash": finding_hash}


@app.get("/tickets")
def list_tickets() -> dict:
    tickets = _provider.all()
    return {"count": len(tickets), "tickets": [t.to_dict() for t in tickets]}


@app.get("/escalations")
def list_escalations() -> dict:
    items = _escalations.list_all()
    return {"count": len(items), "escalations": items}
