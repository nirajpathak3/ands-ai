# Backlog #3 — Cloud FinOps remediation agent (governed cost optimization)

> Agentic cloud-cost optimization that doesn't just *report* waste — it proposes and (with approval)
> *executes* remediation and tracks realized savings. Peers: Vantage, CAST AI, nOps, Cloudability —
> mostly dashboards/reporting; the **governed agentic remediation loop** is underdone. One-line: *an
> agent that finds cloud waste, proposes fixes, gets approval, executes, and proves the savings.*

---

## Problem
Cloud spend is bloated with idle/over-provisioned/orphaned resources. Existing tools surface waste but
stop at a dashboard; humans rarely action it. The gap is the **closed loop**: investigate → propose →
approve → execute → verify savings — exactly where governed agentic automation wins.

## Why agentic
Ingest billing + usage → investigate root cause (multi-step, query metrics) → propose rightsizing /
scheduling / cleanup → confidence-gate (auto-execute safe / approve risky / escalate) → execute via
cloud APIs → track realized savings. Stateful, tool-using, decisioning with HITL on anything
destructive — the governance model is the whole point.

## Target user / buyer
Platform / infra / FinOps teams; eng leadership with a cloud bill they want cut. Clear ROI = the agent
pays for itself. Strong fit for a *platform engineer's* credibility.

## Why my stack fits (reuse ~70%)
- **Confidence-gated governance + HITL** → "auto-execute safe, approve destructive, escalate unknown"
  maps perfectly (`governance.py`, interrupt/resume).
- **Idempotency + DLQ + retry** → safe execution against flaky cloud APIs (`idempotency.py`,
  `ticketing.DeadLetterQueue`).
- **Audit trail + analytics** → every action audited; realized-savings as a read-model
  (`AuditRecord`, `analytics.py`).
- **Scheduler** → continuous waste sweeps (`scheduler.py`).
- **Provider adapters** → cloud APIs behind ports (`providers/` pattern).
- New: cost-data ingestion + remediation playbooks + savings tracker.

## Architecture sketch
Build **via Forge**: Planner (which waste classes) → Investigator (query usage, fan-out) → Proposer
(remediation + risk score) → governance gate → Executor (idempotent, DLQ-protected) → Verifier
(realized savings). Destructive actions always HITL.

## v1 demo scope
Mock billing + usage dataset; agent finds idle instances + oversized volumes; proposes fixes with risk
scores; auto-applies a safe tag/schedule change, routes a delete to human approval; dashboard shows
projected vs. realized savings + full audit of every action.

## Success metric
$ identified vs. $ realized; % actions auto-executed safely vs. approved; zero unaudited destructive
actions.

## 5-year evolution
FinOps → general "ops remediation" agent (the same loop applies to reliability, security, data) →
autonomous operator with an oversight layer. Durable: cost discipline never goes away; governed
auto-remediation is the frontier.

## Key risk
Real execution against cloud is genuinely dangerous (blast radius). Mitigation: demo on mock + dry-run
mode; HITL on all destructive ops; idempotency + DLQ are first-class — and that safety story *is* the
platform-engineer differentiator.
