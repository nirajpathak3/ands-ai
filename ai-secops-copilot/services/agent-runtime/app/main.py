"""FastAPI entrypoint for the agent runtime.

Day-2 walking skeleton (all runnable offline with the deterministic LLM stand-in):
  * GET  /                               - redirect to the operations dashboard
  * GET  /dashboard                      - single-page operations dashboard (Day 8)
  * GET  /metrics                        - platform KPIs (automation rate, latency, ...)
  * POST /demo/seed                      - ingest bundled sample reports (one-click demo)
  * GET  /health                         - liveness + config snapshot
  * POST /governance/preview             - confidence -> disposition (no LLM)
  * POST /analyze                        - full pipeline: Finding -> analysis ->
                                           governance -> action (auto-ticket /
                                           approval queue / escalate)
  * POST /ingest                         - normalize a Semgrep/SARIF report and run
                                           every finding through the pipeline
  * GET  /knowledge/search               - retrieve OWASP/CWE guidance (RAG layer)
  * GET  /audit                          - append-only governance audit trail
  * GET  /approvals                      - list decisions awaiting human approval
  * POST /approvals/{finding_hash}/approve - approve -> create the ticket (HITL)
  * POST /approvals/{finding_hash}/reject  - reject a pending decision
  * GET  /tickets                        - list (mock) tickets created so far
  * GET  /escalations                    - list escalated findings

Run locally:
    uvicorn app.main:app --reload --port 8088
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError

from . import __version__
from .config import get_settings
from .domain import Action
from .governance import evaluate as governance_evaluate
from .ingestion import normalize
from .metrics import compute_metrics
from .pipeline import run_pipeline
from .providers import get_ticket_provider
from .rag import get_retriever
from .schemas import AnalyzeRequest, Finding
from .ticketing import ApprovalStore, AuditLog, DeadLetterQueue, EscalationQueue

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SAMPLES_DIR = _REPO_ROOT / "datasets" / "samples"
_DASHBOARD_HTML = Path(__file__).resolve().parent / "static" / "dashboard.html"

app = FastAPI(
    title="AI Security Operations Copilot - Agent Runtime",
    version=__version__,
    summary="LangGraph agent runtime: Finding Analysis -> Ticket Decision -> Governance Gate.",
)

# Provider is selected from config (mock by default; jira/servicenow when set).
# Day 10 persists approvals via checkpointing.
_provider = get_ticket_provider(get_settings())
_retriever = get_retriever(get_settings())
_approvals = ApprovalStore()
_escalations = EscalationQueue()
_dead_letter = DeadLetterQueue()
_audit = AuditLog()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> HTMLResponse:
    """Single-page operations dashboard (Day 8 demo milestone)."""
    if not _DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="Dashboard asset missing.")
    return HTMLResponse(_DASHBOARD_HTML.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
        "ticketProvider": getattr(_provider, "name", "unknown"),
        "knowledge": {
            "ragEnabled": settings.rag_enabled,
            "retriever": getattr(_retriever, "name", None),
            "documents": len(_retriever) if _retriever is not None else 0,
            "topK": settings.rag_top_k,
        },
        "governance": {
            "autoThreshold": settings.auto_threshold,
            "suggestThreshold": settings.suggest_threshold,
            "suppressAutoThreshold": settings.suppress_auto_threshold,
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
        "reasonCode": decision.reason_code.value,
    }


@app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    """Run a finding through the full walking skeleton and execute the decision."""
    started = time.perf_counter()
    out = run_pipeline(
        req.finding.model_dump(),
        provider=_provider,
        approvals=_approvals,
        escalations=_escalations,
        dead_letter=_dead_letter,
        retriever=_retriever,
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    _audit.record(
        out["decision"], out["action"]["outcome"], actor="system", latency_ms=latency_ms
    )
    return out


class IngestRequest(BaseModel):
    format: str = "auto"  # auto | semgrep | sarif
    report: dict


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    """Normalize a raw scanner report (Semgrep/SARIF) and run each finding.

    The Copilot ingests findings; it does not scan. This maps native scanner output
    to the normalized contract (ADR-007), then drives every finding through the
    full pipeline and returns a per-finding result plus an outcome summary.
    """
    try:
        normalized = normalize(req.report, req.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    results: list[dict] = []
    skipped: list[dict] = []
    summary: dict[str, int] = {}
    for item in normalized:
        try:
            finding = Finding.model_validate(item)
        except ValidationError as exc:
            skipped.append({"id": item.get("id"), "errors": exc.error_count()})
            continue
        started = time.perf_counter()
        out = run_pipeline(
            finding.model_dump(), provider=_provider, approvals=_approvals,
            escalations=_escalations, dead_letter=_dead_letter, retriever=_retriever,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        outcome = out["action"]["outcome"]
        _audit.record(out["decision"], outcome, actor="system", latency_ms=latency_ms)
        summary[outcome] = summary.get(outcome, 0) + 1
        results.append({
            "findingId": out["decision"].get("findingId"),
            "severity": (out["decision"].get("analysis") or {}).get("severity"),
            "disposition": out["decision"].get("disposition"),
            "outcome": outcome,
        })

    return {
        "received": len(normalized),
        "processed": len(results),
        "skipped": len(skipped),
        "summary": summary,
        "results": results,
        "skippedDetail": skipped,
    }


@app.get("/knowledge/search")
def knowledge_search(q: str, k: int = 3) -> dict:
    """Retrieve OWASP/CWE guidance for a free-text query (RAG layer demo, ADR-001)."""
    if _retriever is None:
        raise HTTPException(status_code=503, detail="RAG is disabled (RAG_ENABLED=false).")
    try:
        hits = _retriever.retrieve(q, k=k)
    except Exception as exc:  # noqa: BLE001 - surface backend errors as 503
        raise HTTPException(status_code=503, detail=f"Retriever error: {exc}") from None
    return {
        "query": q,
        "retriever": getattr(_retriever, "name", "unknown"),
        "count": len(hits),
        "results": [
            {**h.to_citation(), "type": h.document.type, "snippet": h.document.text}
            for h in hits
        ],
    }


@app.get("/approvals")
def list_approvals() -> dict:
    pending = _approvals.list_pending()
    return {"count": len(pending), "pending": [p.decision for p in pending]}


@app.post("/approvals/{finding_hash}/approve")
def approve(finding_hash: str) -> dict:
    """Human approves a queued decision -> the ticket is created (HITL gate)."""
    pending = _approvals.get(finding_hash)
    try:
        ticket, created = _approvals.approve(finding_hash, _provider)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No pending approval for {finding_hash}"
        ) from None
    outcome = "ticket_created" if created else "ticket_exists"
    if pending is not None:
        _audit.record(pending.decision, outcome, actor="human")
    return {"outcome": outcome, "approvedBy": "human", "ticket": ticket.to_dict()}


@app.post("/approvals/{finding_hash}/reject")
def reject(finding_hash: str) -> dict:
    pending = _approvals.get(finding_hash)
    if not _approvals.reject(finding_hash):
        raise HTTPException(status_code=404, detail=f"No pending approval for {finding_hash}")
    if pending is not None:
        _audit.record(pending.decision, "rejected", actor="human")
    return {"outcome": "rejected", "findingHash": finding_hash}


@app.get("/tickets")
def list_tickets() -> dict:
    tickets = _provider.all()
    return {"count": len(tickets), "tickets": [t.to_dict() for t in tickets]}


@app.get("/escalations")
def list_escalations() -> dict:
    items = _escalations.list_all()
    return {"count": len(items), "escalations": items}


@app.get("/metrics")
def metrics() -> dict:
    """Platform KPIs for the dashboard (derived from the audit trail + stores)."""
    return compute_metrics(
        _audit.list_all(),
        tickets=len(_provider.all()),
        pending_approvals=len(_approvals.list_pending()),
        escalations=len(_escalations.list_all()),
        dead_letters=len(_dead_letter.list_all()),
    )


@app.post("/demo/seed")
def demo_seed() -> dict:
    """One-click demo: ingest the bundled Semgrep + SARIF sample reports.

    Drives the memorable walkthrough — a critical SQLi auto-creates a ticket while a
    medium finding waits for human approval — without any external scanner or creds.
    """
    seeded: dict[str, dict] = {}
    for name, fmt in (("semgrep-sample.json", "semgrep"), ("sarif-sample.json", "sarif")):
        path = _SAMPLES_DIR / name
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        seeded[name] = ingest(IngestRequest(format=fmt, report=report))
    if not seeded:
        raise HTTPException(status_code=404, detail="No sample reports found to seed.")
    return {"seeded": list(seeded.keys()), "reports": seeded}


@app.get("/audit")
def list_audit() -> dict:
    """Append-only governance audit trail: why each decision was taken, by whom."""
    records = _audit.list_all()
    return {"count": len(records), "records": [r.to_dict() for r in records]}


@app.get("/deadletter")
def list_dead_letter() -> dict:
    """Decisions whose ticket action failed (e.g. Jira API down) — replayable."""
    items = _dead_letter.list_all()
    return {
        "count": len(items),
        "items": [{"findingHash": i.findingHash, "error": i.error} for i in items],
    }
