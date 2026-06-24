"""FastAPI entrypoint for the agent runtime.

Day-2 walking skeleton (all runnable offline with the deterministic LLM stand-in):
  * GET  /                               - redirect to the operations dashboard
  * GET  /dashboard                      - single-page operations dashboard (Day 8)
  * GET  /metrics                        - platform KPIs (automation rate, latency, ...)
  * POST /demo/seed                      - ingest bundled sample reports (one-click demo)
  * POST /demo/reset                     - clear in-memory state (fresh demo slate)
  * GET  /graph                          - compiled LangGraph structure (nodes + mermaid)
  * POST /graph/analyze                  - run via the compiled graph (HITL interrupt)
  * POST /graph/resume/{thread_id}       - resume a paused run (approve/reject)
  * GET  /health                         - liveness + config snapshot
  * POST /governance/preview             - confidence -> disposition (no LLM)
  * POST /analyze                        - full pipeline: Finding -> analysis ->
                                           governance -> action (auto-ticket /
                                           approval queue / escalate)
  * POST /ingest                         - normalize a Semgrep/SARIF report and run
                                           every finding through the pipeline
  * GET  /knowledge/search               - retrieve OWASP/CWE guidance (RAG layer)
  * GET  /findings                       - current-state findings (deduped) + tickets
  * GET  /audit                          - append-only governance audit trail
  * GET  /approvals                      - list decisions awaiting human approval
  * POST /approvals/{finding_hash}/approve - approve -> create the ticket (HITL)
  * POST /approvals/{finding_hash}/reject  - reject a pending decision
  * GET  /tickets                        - list (mock) tickets created so far
  * GET  /escalations                    - list escalated findings
  * GET  /gateway/metrics                - AI Gateway egress metrics (Day 11)
  * GET  /observability/metrics          - Prometheus text exposition (Day 12)
  * GET  /observability/alerts           - firing alerts (governance/cost/reliability)
  * GET  /observability/timeseries       - cost/latency over time (charts)
  * GET  /observability/traces           - recent spans from the in-process tracer
  * GET  /remediation                    - SLA view: per-ticket status + MTTR (Day 16)
  * POST /tickets/{finding_hash}/transition - apply a ticket lifecycle status (Day 16)
  * POST /remediation/sync               - reconcile findings with resolved tickets
  * GET  /notifications                  - recent outbound notifications + channels (Day 17)
  * POST /notifications/sweep            - detect SLA breaches and fire notifications
  * POST /webhooks/tickets               - inbound provider webhook (real-time sync)
  * GET  /jobs                           - background-job status (Day 18)
  * POST /jobs/run/{name}                - run a background job once, on demand

Run locally (use `python -m` so it works even when the uvicorn script isn't on PATH):
    python -m uvicorn app.main:app --reload --port 8088
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError

from . import __version__
from .auth import AuthError, Principal, authenticate
from .config import Settings, get_settings
from .domain import Action
from .governance import evaluate as governance_evaluate
from .ingestion import normalize
from .metrics import compute_metrics, project_findings
from .notifications import parse_ticket_webhook, verify_signature
from .observability import (
    configure_logging,
    default_rules,
    evaluate_alerts,
    get_timeseries,
    get_tracer,
    render_prometheus,
    reset_observability,
)
from .pipeline import run_pipeline
from .rag import get_retriever
from .ratelimit import get_rate_limiter
from .remediation import RESOLVED_STATUSES, VALID_STATUSES, build_remediation
from .scheduler import Scheduler
from .schemas import AnalyzeRequest, Finding
from .tenancy import TenantContext, TenantRegistry
from .ticketing import execute_decision

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SAMPLES_DIR = _REPO_ROOT / "datasets" / "samples"
_DASHBOARD_HTML = Path(__file__).resolve().parent / "static" / "dashboard.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background scheduler on boot (if enabled) and stop it on shutdown."""
    _register_jobs()
    if get_settings().scheduler_enabled:
        _scheduler.start()
    yield
    await _scheduler.stop()


app = FastAPI(
    title="AI Security Operations Copilot - Agent Runtime",
    version=__version__,
    summary="LangGraph agent runtime: Finding Analysis -> Ticket Decision -> Governance Gate.",
    lifespan=lifespan,
)

configure_logging(get_settings())  # structured JSON logs + trace context (Day 12)

# Shared, safe-to-share singletons: the read-only RAG corpus and the process-wide
# observability tracer/time-series (operator telemetry across tenants).
_retriever = get_retriever(get_settings())
_timeseries = get_timeseries()  # rolling cost/latency series (Day 12)
_tracer = get_tracer(get_settings())

# Per-tenant isolated state (Day 15): audit/approvals/escalations/dead-letter, ticket
# provider, AI Gateway (cache + cost), and compiled graph — one set per tenant, built
# lazily. With auth disabled every request resolves to ``default_tenant``.
_registry = TenantRegistry(get_settings())
_rate_limiter = get_rate_limiter()

# In-process background scheduler (Day 18); jobs are registered at import so on-demand runs
# work in tests/offline, and the periodic loops start only when SCHEDULER_ENABLED=true.
_scheduler = Scheduler()


_SettingsDep = Annotated[Settings, Depends(get_settings)]


def _principal(request: Request, settings: _SettingsDep) -> Principal:
    """Authenticate the request into a tenant principal (or 401/403)."""
    try:
        return authenticate(request.headers, settings)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def get_ctx(
    principal: Annotated[Principal, Depends(_principal)],
    settings: _SettingsDep,
) -> TenantContext:
    """Rate-limit, then resolve the caller's isolated tenant context (Day 15)."""
    result = _rate_limiter.check(principal.tenant_id, settings.rate_limit_rpm)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(int(result.retry_after_s) + 1)},
        )
    return _registry.get(principal.tenant_id)


# Type alias so endpoints declare `ctx: CtxDep` (avoids a Depends() call in defaults).
CtxDep = Annotated[TenantContext, Depends(get_ctx)]


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
    """Liveness + config snapshot (no auth; used by the container healthcheck).

    Backend details are reported for the default tenant; per-tenant data is only ever
    served through the authenticated, tenant-scoped endpoints.
    """
    settings = get_settings()
    ctx = _registry.get(settings.default_tenant)
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
        "ticketProvider": getattr(ctx.provider, "name", "unknown"),
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
        "orchestration": "langgraph" if ctx.graph_runner is not None else "inline",
        "persistence": ctx.state.backend,
        "tenancy": {
            "authEnabled": settings.auth_enabled,
            "defaultTenant": settings.default_tenant,
            "activeTenants": len(_registry.ids()),
            "rateLimitRpm": settings.rate_limit_rpm,
        },
        "llm": {
            "egress": "gateway",
            "providers": ctx.gateway.metrics()["providers"],
            "cacheEnabled": settings.llm_cache_enabled,
        },
        "observability": {
            "tracing": "otel" if settings.otel_enabled else "in-process",
            "logJson": settings.log_json,
            "alertsFiring": len(
                evaluate_alerts(_obs_snapshot(ctx), default_rules(settings))
            ),
        },
    }


@app.get("/gateway/metrics")
def gateway_metrics(ctx: CtxDep) -> dict:
    """AI Gateway egress metrics: requests, cache hits, fallbacks, cost, latency (Day 11)."""
    return ctx.gateway.metrics()


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
def analyze(req: AnalyzeRequest, ctx: CtxDep) -> dict:
    """Run a finding through the full walking skeleton and execute the decision."""
    started = time.perf_counter()
    out = run_pipeline(
        req.finding.model_dump(),
        provider=ctx.provider,
        approvals=ctx.approvals,
        escalations=ctx.escalations,
        dead_letter=ctx.dead_letter,
        retriever=_retriever,
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    ctx.audit.record(
        out["decision"], out["action"]["outcome"], actor="system", latency_ms=latency_ms
    )
    _observe_decision(out["decision"], out["action"]["outcome"], latency_ms)
    _notify_outcome(ctx, out["decision"], out["action"]["outcome"])
    return out


class IngestRequest(BaseModel):
    format: str = "auto"  # auto | semgrep | sarif
    report: dict


def _run_ingest(report: dict, fmt: str, ctx: TenantContext) -> dict:
    """Normalize a scanner report and drive every finding through this tenant's pipeline."""
    try:
        normalized = normalize(report, fmt)
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
            finding.model_dump(), provider=ctx.provider, approvals=ctx.approvals,
            escalations=ctx.escalations, dead_letter=ctx.dead_letter, retriever=_retriever,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        outcome = out["action"]["outcome"]
        ctx.audit.record(out["decision"], outcome, actor="system", latency_ms=latency_ms)
        _observe_decision(out["decision"], outcome, latency_ms)
        _notify_outcome(ctx, out["decision"], outcome)
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


@app.post("/ingest")
def ingest(req: IngestRequest, ctx: CtxDep) -> dict:
    """Normalize a raw scanner report (Semgrep/SARIF) and run each finding.

    The Copilot ingests findings; it does not scan. This maps native scanner output
    to the normalized contract (ADR-007), then drives every finding through the
    full pipeline and returns a per-finding result plus an outcome summary.
    """
    return _run_ingest(req.report, req.format, ctx)


@app.get("/knowledge/search")
def knowledge_search(
    ctx: CtxDep, q: str, k: int = 3
) -> dict:
    """Retrieve OWASP/CWE guidance for a free-text query (RAG layer demo, ADR-001).

    The knowledge corpus is shared (the same OWASP/CWE for every tenant); the endpoint
    is still authenticated and rate-limited like the rest of the data plane.
    """
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
def list_approvals(ctx: CtxDep) -> dict:
    pending = ctx.approvals.list_pending()
    return {"count": len(pending), "pending": [p.decision for p in pending]}


@app.post("/approvals/{finding_hash}/approve")
def approve(finding_hash: str, ctx: CtxDep) -> dict:
    """Human approves a queued decision -> the ticket is created (HITL gate)."""
    pending = ctx.approvals.get(finding_hash)
    try:
        ticket, created = ctx.approvals.approve(finding_hash, ctx.provider)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No pending approval for {finding_hash}"
        ) from None
    outcome = "ticket_created" if created else "ticket_exists"
    if pending is not None:
        ctx.audit.record(pending.decision, outcome, actor="human")
    return {"outcome": outcome, "approvedBy": "human", "ticket": ticket.to_dict()}


@app.post("/approvals/{finding_hash}/reject")
def reject(finding_hash: str, ctx: CtxDep) -> dict:
    pending = ctx.approvals.get(finding_hash)
    if not ctx.approvals.reject(finding_hash):
        raise HTTPException(status_code=404, detail=f"No pending approval for {finding_hash}")
    if pending is not None:
        ctx.audit.record(pending.decision, "rejected", actor="human")
    return {"outcome": "rejected", "findingHash": finding_hash}


@app.get("/tickets")
def list_tickets(ctx: CtxDep) -> dict:
    tickets = ctx.provider.all()
    return {"count": len(tickets), "tickets": [t.to_dict() for t in tickets]}


@app.get("/escalations")
def list_escalations(ctx: CtxDep) -> dict:
    items = ctx.escalations.list_all()
    return {"count": len(items), "escalations": items}


@app.get("/metrics")
def metrics(ctx: CtxDep) -> dict:
    """Platform KPIs for the dashboard (derived from the audit trail + stores)."""
    return compute_metrics(
        ctx.audit.list_all(),
        tickets=len(ctx.provider.all()),
        pending_approvals=len(ctx.approvals.list_pending()),
        escalations=len(ctx.escalations.list_all()),
        dead_letters=len(ctx.dead_letter.list_all()),
    )


def _notify_outcome(ctx: TenantContext, decision: dict, outcome: str) -> None:
    """Emit an outbound notification for human-actionable outcomes (Day 17).

    Escalations and approval-required outcomes page a human; deduped per finding so
    re-ingesting the same report never spams the channels.
    """
    finding_hash = str(decision.get("findingHash") or "") or None
    finding_id = decision.get("findingId")
    analysis = decision.get("analysis") or {}
    severity = str(analysis.get("severity", "unknown"))
    label = finding_id or (finding_hash or "")[:8]
    if outcome == "escalated":
        ctx.notifications.emit(
            "escalation",
            title=f"Finding escalated ({severity})",
            message=f"{label}: routed to a human analyst (ambiguous / low confidence).",
            finding_hash=finding_hash, finding_id=finding_id,
        )
    elif outcome == "pending_approval":
        ctx.notifications.emit(
            "approval_required",
            title=f"Approval required ({severity})",
            message=f"{label}: awaiting human approval before action.",
            finding_hash=finding_hash, finding_id=finding_id,
        )


def _observe_decision(decision: dict, outcome: str, latency_ms: float) -> None:
    """Push a governed decision onto the rolling time-series (Day 12)."""
    analysis = decision.get("analysis") or {}
    _timeseries.record_decision(
        disposition=str(decision.get("disposition", "")),
        severity=str(analysis.get("severity", "unknown")),
        latency_ms=latency_ms,
        outcome=outcome,
    )


def _obs_snapshot(ctx: TenantContext) -> dict:
    """Combined snapshot (KPIs + gateway) that alerts + Prometheus evaluate against."""
    snap = compute_metrics(
        ctx.audit.list_all(),
        tickets=len(ctx.provider.all()),
        pending_approvals=len(ctx.approvals.list_pending()),
        escalations=len(ctx.escalations.list_all()),
        dead_letters=len(ctx.dead_letter.list_all()),
    )
    snap["gateway"] = ctx.gateway.metrics()
    return snap


@app.get("/observability/alerts")
def observability_alerts(ctx: CtxDep) -> dict:
    """Firing alerts over governance/cost/reliability signals (Day 12, ADR-015)."""
    alerts = evaluate_alerts(_obs_snapshot(ctx), default_rules(get_settings()))
    return {"count": len(alerts), "alerts": alerts}


@app.get("/observability/metrics")
def observability_metrics(ctx: CtxDep) -> PlainTextResponse:
    """Prometheus text exposition of platform + gateway metrics and alert states."""
    snapshot = _obs_snapshot(ctx)
    alerts = evaluate_alerts(snapshot, default_rules(get_settings()))
    return PlainTextResponse(render_prometheus(snapshot, alerts))


@app.get("/observability/timeseries")
def observability_timeseries(
    ctx: CtxDep,
    window_s: float = 300.0,
    bucket_s: float = 30.0,
) -> dict:
    """Bucketed cost/latency over time for charting (LLM calls + decisions).

    The time-series is process-wide operator telemetry (shared across tenants); the
    endpoint is authenticated like the rest of the data plane.
    """
    return {
        "windowS": window_s,
        "bucketS": bucket_s,
        "llm": _timeseries.buckets("llm", window_s=window_s, bucket_s=bucket_s),
        "decisions": _timeseries.buckets("decision", window_s=window_s, bucket_s=bucket_s),
        "recentLlm": _timeseries.recent("llm", limit=60),
    }


@app.get("/observability/traces")
def observability_traces(
    ctx: CtxDep, limit: int = 50
) -> dict:
    """Recent spans from the in-process tracer (newest first; process-wide)."""
    return {"count": min(limit, 512), "spans": _tracer.recent(limit)}


@app.post("/demo/seed")
def demo_seed(ctx: CtxDep) -> dict:
    """One-click demo: ingest the bundled Semgrep + SARIF sample reports.

    Drives the memorable walkthrough — a critical SQLi auto-creates a ticket while a
    medium finding waits for human approval — without any external scanner or creds.
    Seeds into the caller's tenant only.
    """
    seeded: dict[str, dict] = {}
    for name, fmt in (("semgrep-sample.json", "semgrep"), ("sarif-sample.json", "sarif")):
        path = _SAMPLES_DIR / name
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        seeded[name] = _run_ingest(report, fmt, ctx)
    if not seeded:
        raise HTTPException(status_code=404, detail="No sample reports found to seed.")
    return {"seeded": list(seeded.keys()), "reports": seeded}


@app.post("/demo/reset")
def demo_reset(ctx: CtxDep) -> dict:
    """Clear the caller's tenant state (audit, approvals, escalations, dead-letters, tickets).

    The audit trail is intentionally append-only, so re-seeding accumulates events; this
    truncates the stores to a clean slate (in place, so it works for the durable SQLite/
    Postgres backends too — unlike a process restart, which now *keeps* persisted state).
    Idempotent ticket creation means re-seeding never duplicates tickets. Rebuilds the
    tenant's gateway (drops cache + metrics) and graph checkpointer; clears the shared
    observability buffers.
    """
    new_ctx = _registry.reset(ctx.tenant_id)  # truncate stores + rebuild gateway/graph
    reset_observability(get_settings())        # clear traces + time-series (shared)
    return {"status": "reset", "tenant": new_ctx.tenant_id, "backend": new_ctx.state.backend}


class GraphResumeRequest(BaseModel):
    approved: bool


@app.get("/graph", include_in_schema=True)
def graph_structure(ctx: CtxDep) -> dict:
    """Introspect the compiled LangGraph (nodes + mermaid) — the orchestration story."""
    if ctx.graph_runner is None:
        raise HTTPException(status_code=503, detail="LangGraph is not installed.")
    return {"nodes": ctx.graph_runner.nodes(), "mermaid": ctx.graph_runner.mermaid()}


@app.post("/graph/analyze")
def graph_analyze(req: AnalyzeRequest, ctx: CtxDep) -> dict:
    """Run a finding through the compiled graph (conditional routing + HITL interrupt).

    Returns a completed result, or ``status=awaiting_approval`` with a ``threadId`` to
    resume via ``POST /graph/resume/{thread_id}`` — durable human-in-the-loop.
    """
    if ctx.graph_runner is None:
        raise HTTPException(status_code=503, detail="LangGraph is not installed.")
    started = time.perf_counter()
    out = ctx.graph_runner.analyze(
        req.finding.model_dump(), client=None, retriever=_retriever
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    decision = out.get("decision") or {}
    outcome = out["action"]["outcome"] if out["status"] == "completed" else "pending_approval"
    ctx.audit.record(decision, outcome, actor="system", latency_ms=latency_ms)
    _observe_decision(decision, outcome, latency_ms)
    _notify_outcome(ctx, decision, outcome)
    return out


@app.post("/graph/resume/{thread_id}")
def graph_resume(
    thread_id: str, req: GraphResumeRequest, ctx: CtxDep
) -> dict:
    """Resume a paused graph run with the human's approve/reject (checkpointed HITL)."""
    if ctx.graph_runner is None:
        raise HTTPException(status_code=503, detail="LangGraph is not installed.")
    try:
        out = ctx.graph_runner.resume(thread_id, approved=req.approved)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No paused run for thread {thread_id}"
        ) from None
    decision = out.get("decision") or {}
    if out.get("action"):
        ctx.audit.record(decision, out["action"]["outcome"], actor="human")
    return out


@app.get("/findings")
def list_findings(ctx: CtxDep) -> dict:
    """Current-state findings (deduped by finding_hash), each with its linked ticket.

    This is the materialized view over the append-only audit trail: re-ingesting the
    same report updates a finding in place (and bumps its `evaluations` count) instead
    of adding a duplicate row. A finding has at most one ticket (idempotency), so a
    Jira/ServiceNow link shows exactly once here.
    """
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


@app.get("/audit")
def list_audit(ctx: CtxDep) -> dict:
    """Append-only governance audit trail: why each decision was taken, by whom."""
    records = ctx.audit.list_all()
    return {"count": len(records), "records": [r.to_dict() for r in records]}


@app.get("/deadletter")
def list_dead_letter(ctx: CtxDep) -> dict:
    """Decisions whose ticket action failed (e.g. Jira API down) — replayable."""
    items = ctx.dead_letter.list_all()
    return {
        "count": len(items),
        "items": [{"findingHash": i.findingHash, "error": i.error} for i in items],
    }


# --- Day 16: ticket lifecycle sync + remediation tracking -------------------

class TransitionRequest(BaseModel):
    status: str


def _latest_audit_by_hash(ctx: TenantContext) -> dict:
    latest = {}
    for r in ctx.audit.list_all():
        latest[r.findingHash] = r
    return latest


def _record_resolution(ctx: TenantContext, finding_hash: str) -> bool:
    """Append a ``ticket_resolved`` audit event for a finding (idempotent).

    Reconstructs the decision from the finding's latest audit record so the
    current-state findings view reflects resolution and the compliance log keeps the
    full lifecycle. Returns True if a new event was recorded.
    """
    latest = _latest_audit_by_hash(ctx).get(finding_hash)
    if latest is None or latest.outcome == "ticket_resolved":
        return False
    decision = {
        "findingHash": latest.findingHash,
        "findingId": latest.findingId,
        "disposition": latest.disposition,
        "reasonCode": latest.reasonCode,
        "analysis": {
            "severity": latest.severity,
            "confidence": latest.confidence,
            "recommendedAction": latest.recommendedAction,
        },
    }
    ctx.audit.record(decision, "ticket_resolved", actor="provider")
    label = latest.findingId or finding_hash[:8]
    ctx.notifications.emit(
        "ticket_resolved",
        title=f"Finding resolved ({latest.severity})",
        message=f"{label}: ticket closed; remediation complete.",
        finding_hash=finding_hash, finding_id=latest.findingId,
    )
    return True


@app.get("/remediation")
def remediation(ctx: CtxDep) -> dict:
    """Remediation view: every ticket with its SLA status, age, and MTTR (Day 16).

    Joins current-state findings with their tickets, computes per-severity SLA budgets,
    and summarizes the portfolio (open vs resolved, breached/at-risk, SLA compliance,
    mean time-to-remediate).
    """
    findings = project_findings(ctx.audit.list_all())
    by_hash = {f["findingHash"]: f for f in findings}
    tickets = [t.to_dict() for t in ctx.provider.all()]
    return build_remediation(by_hash, tickets)


@app.post("/tickets/{finding_hash}/transition")
def transition_ticket(
    finding_hash: str, req: TransitionRequest, ctx: CtxDep
) -> dict:
    """Apply a ticket lifecycle status (the inbound half of bi-directional sync).

    Models an external system (Jira/ServiceNow) or a human moving the ticket — e.g.
    ``resolved``. On a resolving transition the finding is marked resolved in the audit
    trail so the current-state view and remediation metrics reflect closure.
    """
    status = req.status.strip().lower()
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Valid: {sorted(VALID_STATUSES)}",
        )
    ticket = ctx.provider.transition(finding_hash, status)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket for finding {finding_hash}")
    resolved = status in RESOLVED_STATUSES
    if resolved:
        _record_resolution(ctx, finding_hash)
    return {"ticket": ticket.to_dict(), "resolved": resolved}


def _reconcile_resolved(ctx: TenantContext) -> int:
    """Record resolution for any terminal-status ticket not yet marked resolved."""
    reconciled = 0
    for t in ctx.provider.all():
        if t.status in RESOLVED_STATUSES and _record_resolution(ctx, t.findingHash):
            reconciled += 1
    return reconciled


@app.post("/remediation/sync")
def remediation_sync(ctx: CtxDep) -> dict:
    """Reconcile findings with resolved tickets (e.g. after polling a real provider).

    Idempotently records a ``ticket_resolved`` audit event for any ticket already in a
    terminal state whose finding isn't yet marked resolved — so an out-of-band closure
    (a developer closing the Jira issue) flows back into the platform's state.
    """
    return {"reconciled": _reconcile_resolved(ctx)}


# --- Day 17: notifications & webhooks ---------------------------------------

@app.get("/notifications")
def list_notifications(ctx: CtxDep, limit: int = 50) -> dict:
    """Recent outbound notifications (newest first) + the active channels."""
    items = ctx.notifications.list_recent(limit)
    return {
        "count": len(items),
        "channels": ctx.notifications.channels,
        "notifications": [n.to_dict() for n in items],
    }


def _sweep_breaches(ctx: TenantContext) -> dict:
    """Detect SLA breaches and fire a (deduped) ``sla_breach`` notification for each."""
    findings = project_findings(ctx.audit.list_all())
    by_hash = {f["findingHash"]: f for f in findings}
    tickets = [t.to_dict() for t in ctx.provider.all()]
    view = build_remediation(by_hash, tickets)
    breaches = [i for i in view["items"] if i["slaStatus"] == "breached"]
    notified = 0
    for item in breaches:
        label = item.get("findingId") or (item.get("findingHash") or "")[:8]
        fired = ctx.notifications.emit(
            "sla_breach",
            title=f"SLA breached ({item['severity']})",
            message=f"{label}: ticket {item.get('ticketKey')} is past its "
                    f"{item.get('slaHours')}h SLA.",
            finding_hash=item.get("findingHash"), finding_id=item.get("findingId"),
        )
        if fired is not None:
            notified += 1
    return {"breaches": len(breaches), "notified": notified}


@app.post("/notifications/sweep")
def notifications_sweep(ctx: CtxDep) -> dict:
    """Detect SLA breaches now and fire a (deduped) ``sla_breach`` notification each.

    Designed to be called on a schedule (or on dashboard refresh): turns the passive SLA
    view into active paging without a background worker.
    """
    return _sweep_breaches(ctx)


class WebhookResponse(BaseModel):
    ok: bool
    tenant: str
    findingHash: str
    status: str
    resolved: bool


@app.post("/webhooks/tickets")
async def ticket_webhook(request: Request, settings: _SettingsDep) -> WebhookResponse:
    """Inbound provider webhook for real-time ticket lifecycle sync (Day 17).

    Accepts generic / Jira / ServiceNow payloads, maps them to a finding + lifecycle
    status, and applies the transition (marking the finding resolved on closure). This
    endpoint is **not** behind the API-key/JWT data-plane auth — external systems sign
    the body instead: when ``WEBHOOK_SECRET`` is set, a valid ``X-Signature`` HMAC-SHA256
    header is required.
    """
    raw = await request.body()
    signature = request.headers.get("X-Signature") or request.headers.get(
        "X-Hub-Signature-256"
    )
    if not verify_signature(settings.webhook_secret, raw, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None

    finding_hash, status, tenant = parse_ticket_webhook(payload)
    tenant = tenant or request.headers.get("X-Tenant-Id") or settings.default_tenant
    if not finding_hash or not status:
        raise HTTPException(
            status_code=400, detail="Webhook missing a finding hash or recognizable status"
        )
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unsupported status '{status}'")

    ctx = _registry.get(tenant)
    ticket = ctx.provider.transition(finding_hash, status)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket for finding {finding_hash}")
    resolved = status in RESOLVED_STATUSES
    if resolved:
        _record_resolution(ctx, finding_hash)
    return WebhookResponse(
        ok=True, tenant=tenant, findingHash=finding_hash,
        status=status, resolved=resolved,
    )


# --- Day 18: scheduled jobs / background workers ----------------------------

def _retry_dead_letters(ctx: TenantContext) -> dict:
    """Replay dead-lettered decisions through the ticketing layer.

    Drains the queue and re-runs each decision; ``execute_decision`` re-adds any that fail
    again (e.g. the provider is still down), so the operation is safe to repeat.
    """
    items = ctx.dead_letter.list_all()
    if not items:
        return {"retried": 0, "recovered": 0}
    ctx.dead_letter.clear()
    retried = recovered = 0
    for item in items:
        retried += 1
        result = execute_decision(
            item.decision, provider=ctx.provider, approvals=ctx.approvals,
            escalations=ctx.escalations, dead_letter=ctx.dead_letter,
        )
        if result.outcome != "ticket_failed":
            recovered += 1
    return {"retried": retried, "recovered": recovered}


def _for_each_tenant(fn) -> dict:
    """Run a per-tenant chore across every active tenant and aggregate the counters."""
    tenants = _registry.ids()
    totals: dict[str, int] = {}
    for tid in tenants:
        result = fn(_registry.get(tid))
        for key, value in result.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    return {"tenants": len(tenants), **totals}


async def _job_sla_sweep() -> dict:
    return _for_each_tenant(_sweep_breaches)


async def _job_provider_reconcile() -> dict:
    return _for_each_tenant(lambda ctx: {"reconciled": _reconcile_resolved(ctx)})


async def _job_deadletter_retry() -> dict:
    return _for_each_tenant(_retry_dead_letters)


_JOBS_REGISTERED = False


def _register_jobs() -> None:
    """Register the periodic jobs (idempotent; called at import and on lifespan start)."""
    global _JOBS_REGISTERED
    if _JOBS_REGISTERED:
        return
    settings = get_settings()
    _scheduler.register("sla_sweep", settings.sla_sweep_interval_s, _job_sla_sweep)
    _scheduler.register(
        "provider_reconcile", settings.reconcile_interval_s, _job_provider_reconcile
    )
    _scheduler.register(
        "deadletter_retry", settings.deadletter_retry_interval_s, _job_deadletter_retry
    )
    _JOBS_REGISTERED = True


@app.get("/jobs")
def list_jobs() -> dict:
    """Background-job status: interval, run/error counts, last result + timing (Day 18)."""
    settings = get_settings()
    return {
        "schedulerEnabled": settings.scheduler_enabled,
        "running": _scheduler.is_running,
        "jobs": _scheduler.status(),
    }


@app.post("/jobs/run/{name}")
async def run_job_now(name: str) -> dict:
    """Run a background job once, on demand (no waiting for the timer).

    The same code path the periodic loop uses — handy for demos, ops, and tests. Operates
    across all active tenants; in production this would be an admin-scoped action.
    """
    try:
        state = await _scheduler.run_job(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No such job '{name}'. Known: {_scheduler.names}"
        ) from None
    return state.to_dict()


_register_jobs()
