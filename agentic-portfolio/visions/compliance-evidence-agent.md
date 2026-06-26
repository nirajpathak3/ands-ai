# Backlog #1 — Continuous compliance-evidence & control-monitoring agent

> Agentic SOC2 / ISO 27001 / HIPAA evidence collection and continuous control monitoring. Peers: Vanta,
> Drata, Secureframe — but those are checklist/integration tools; the **agentic, investigative,
> continuously-reasoning** layer is still underbaked. One-line: *an agent that continuously gathers
> evidence across your systems, maps it to controls, flags gaps, drafts remediation, and keeps an
> audit-grade trail.*

---

## Problem
Compliance is expensive, manual, and point-in-time. Teams scramble before audits to screenshot
configs, collect logs, and map them to controls. Evidence goes stale; gaps surface late; auditors want
defensible provenance. This is high-value, painful, recurring back-office work generic LLMs do poorly
because it needs multi-step investigation, tool access, and an audit trail — not Q&A.

## Why agentic
Plan controls to verify → gather evidence via tools (cloud APIs, repo, IdP, ticketing) → reason about
sufficiency → flag gaps → draft remediation → escalate uncertain calls to a human → append evidence
with provenance. Stateful, multi-step, tool-using, governed, auditable.

## Target user / buyer
Compliance / GRC leads and security engineers at scaling startups and mid-market; vCISOs. Buyer pays
real money (audits cost $20k–$100k+; tools are $10k–$50k/yr).

## Why my stack fits (reuse ~70%)
- **Governance + audit trail + reasonCode** → maps directly to control-pass/fail/needs-human with
  defensible provenance (`governance.py`, append-only `AuditRecord`, CQRS read models).
- **RAG** over a controls KB (SOC2 CC-series, ISO Annex A, HIPAA safeguards) instead of OWASP/CWE
  (`rag/` seam, same shape).
- **Policy-as-code** → control-specific deterministic rules (`policy.py`).
- **Scheduler** → continuous re-evaluation / drift detection (`scheduler.py`).
- **Provider adapters** → evidence sources behind the same ports pattern (`providers/`).
- **Eval harness** → score evidence-sufficiency judgments; regression-gate prompt changes.
- New: connectors to evidence sources + control-mapping logic + auditor-facing report.

## Architecture sketch
Build it **via Forge** (it's a natural multi-agent job): Planner (which controls) → Collector
(tool-using evidence gathering, fan-out) → Mapper (evidence→control) → Critic (sufficiency, gated) →
HITL approve → audited evidence store + Markdown audit report (reuse `analytics/report`).

## v1 demo scope
3–4 SOC2 controls; mock connectors (cloud config JSON, repo settings, IdP export); agent gathers,
maps, flags 1 gap, drafts remediation, escalates 1 borderline control to human; outputs an audit-grade
report with provenance + citations.

## Success metric
% controls with fresh, provenance-backed evidence; gaps surfaced before audit; auditor can trace every
"pass" to its evidence and reason.

## 5-year evolution
SOC2 evidence → multi-framework continuous control monitoring → autonomous remediation (with HITL) →
the "continuous assurance" layer. Durable: regulation only grows; evidence + audit trail + oversight is
exactly the unsolved pain.

## Key risk
Connector breadth is the moat *and* the cost. Mitigation: nail 3 controls deeply with mock+1 real
connector; sell the agentic reasoning + audit story, not connector count.
