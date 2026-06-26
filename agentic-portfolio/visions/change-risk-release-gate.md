# Project-2 alternative — Change-risk / autonomous release gate

> "Should we ship this change?" An agent that investigates a proposed deployment — diff, dependencies,
> vuln findings, incident history, ownership, blast radius — and returns a governed verdict (allow /
> approve / block) with evidence and an audit trail. Peers (emerging, **not** novel): Koalr,
> DeployWhisper, PRism, ImpactTrace. One-line: *a governed pre-deploy decision plane that predicts blast
> radius and gates risky changes with an audited reason.*

---

## Problem
Teams ship changes blind to downstream risk. Existing signals (SAST, coverage, CODEOWNERS, incident
history, dependency graph) are scattered and rarely fused into one *defensible* go/no-go. AI-generated
IaC/code makes this worse. The gap is the **closed, governed decision**: investigate → score risk →
allow/approve/block → audit — exactly where my governed-automation substrate wins.

## Why agentic (not a chatbot)
Multi-step, tool-using, stateful, decisioning: pull the diff → build/query the dependency graph →
correlate changed files with past incidents (semantic) → ingest scanner findings (SARIF) → compute blast
radius → confidence/materiality gate (auto-allow safe / human-approve risky / block critical) →
deterministic policy override → append-only audit with `reasonCode` → generate a rollback brief.

## Target user / buyer
Platform / release-engineering / DevSecOps teams; eng leadership owning change-failure rate and MTTR.
Strong **platform-engineer** credibility; nudges my identity toward platform/release-eng, not just AppSec.

## Why my stack fits (reuse ~70%)
- **Confidence/materiality governance + reasonCode** → allow/approve/block disposition (`governance.py`).
- **Durable HITL** → human approval on risky changes (`graph/runner.py` interrupt/resume).
- **Policy-as-code** → deterministic gates (e.g. "DB migration on Friday → block") (`policy.py`).
- **RAG** → incident-history correlation instead of OWASP/CWE (`rag/` seam).
- **Ingestion anti-corruption layer** → SARIF/scanner findings as evidence (`ingestion/`).
- **Append-only audit + analytics** → defensible "why" + change-failure metrics (`AuditRecord`).
- **AI Gateway, eval harness, observability** → cost control, scored verdicts, traces.
- New: dependency-graph builder + blast-radius scorer + diff analyst + rollback-brief generator.

## Architecture sketch
Build **via Forge**: Planner (which risk classes) → Diff Analyst + History Agent + Dependency/Blast
Agent + Coverage Agent (fan-out) → Verdict node (governance + policy → allow/approve/block) → audited
report + rollback brief. Target repo/CI behind ports; offline-demoable on a fixture repo + synthetic
incident history.

## v1 demo scope (fully offline)
A fixture repo + seeded incident history. Open a PR touching `payments`: agent shows blast radius
(N transitive callers, M endpoints), correlates "this file was in 4 of last 8 incidents," ingests a
seeded SARIF finding, and returns **block** with audited reasons + rollback brief; a low-risk PR returns
**auto-allow**; a medium PR routes to **human approve** (HITL). CI gate result emitted.

## Demo "wow"
1. Risky PR → **blocked**, with evidence (blast radius + incident match + scanner finding) and a
   `reasonCode` — "it explained *why*, not just a score."
2. Low-risk PR → auto-allowed; medium → human approve in one click.
3. Open the audit: full reasoning chain. *"This is a governed release gate — evidence-first, not a
   black-box risk number."*

## Success metric
Every verdict carries audited, evidence-backed reasons; risky changes never auto-allow; demonstrated
block on a seeded high-risk change; runs as a CI gate in < N minutes.

## 5-year evolution
Release gate → autonomous release management (the same investigate→decide→audit loop) → part of the
oversight/verifier plane. Durable: change risk never goes away; governed auto-gating is the frontier.

## Key risk
Emerging-crowded (Koalr/DeployWhisper/PRism) and still security-adjacent. Mitigation: lead with the
**governed + explainable + audited** angle (incumbents lean on opaque scores), and the
release-engineering framing to broaden identity beyond AppSec.
