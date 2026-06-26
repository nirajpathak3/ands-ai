# Secondary — Explainable AI triage & correlation plane (in front of ticketing producers)

> **STATUS (2026-06-26): demo-only / Project-2 fallback.** Verified to be a *commodity ASPM feature*
> (ArmorCode/Aikido/Cycode/Ox) — a strong interview demo but weak as a product. Priority superseded by
> [`../BACKLOG.md`](../BACKLOG.md) and [`../ROADMAP.md`](../ROADMAP.md).

> Project 2. Highest reuse of my existing security stack (~85%) and the one that leans on a moat no
> other candidate has: real ASPM multi-producer / multi-vendor ticketing experience (Ox). Category
> peers: Aikido AutoTriage, ArmorCode AI-correlation lane. One-line: *a decision plane that sits in
> front of N scanners, dedupes/correlates across producers, and decides real / suppress / needs-human
> with an audited reason — before a ticket is ever cut.*

---

## Problem
Enterprises run many scanners (SAST/SCA/secrets/container/cloud). They emit overlapping, duplicate,
and noisy findings. Today a human (or brittle rules) decides what's real, what's a dup, and what's
worth a ticket. The result: alert fatigue, duplicate tickets, suppressed real vulns, and no defensible
"why." This is *exactly* the pain my Ox/ASPM background is about.

## Why agentic (not a chatbot)
Multi-step, stateful, decisioning with guardrails: normalize → ground (RAG) → reason (LLM) →
**cross-producer correlate + dedup** → confidence-gated disposition (real / suppress / needs-human) →
deterministic policy override → append-only audit with a machine reason code. It acts (suppress / cut
ticket / route to human) and is accountable for it.

## Target user / buyer
AppSec / SecOps leads at mid-to-large orgs drowning in multi-scanner noise; DevSecOps platform teams.
Buyer = security leadership measured on MTTR, false-positive rate, and audit defensibility.

## What's new vs. my existing copilot (keeps it a distinct product)
The copilot is single-producer triage→ticket. This is a **multi-producer correlation/dedup +
explainability plane** — a "trust layer" in front of ticketing, an emerging durable category. Net-new
is small and high-impact:
- **Cross-producer correlation/dedup**: collapse N findings about the same root cause into one
  decision (extends `idempotency.finding_hash` to a fuzzy/structural correlation key).
- **Explainability UI**: per-decision "why real / why suppressed / why human" with citations + the
  contributing producers.

## Architecture (reuse-mapped)

| Component | Reuses | New |
| --- | --- | --- |
| Ingest N producers → canonical `Finding` | `ingestion/` (Semgrep + SARIF anti-corruption layer) | +1–2 more producer adapters |
| Correlate + dedup across producers | `idempotency.py` (`finding_hash`) | correlation key (structural/fuzzy) |
| Ground + reason → validated verdict | `rag/`, `llm.analyze_and_validate`, `schemas.py`, `prompts.py` | — |
| Disposition: real / suppress / needs-human | `governance.py` (asymmetric thresholds, reasonCode) | relabel 3 dispositions |
| Deterministic overrides | `policy.py` (first-match) | — |
| Audited "why" + event log | append-only `AuditRecord`, CQRS read models | explainability projection |
| Cross-producer dashboard + dedup view | dashboard SPA, `analytics.py` | correlation/explainability UI |
| AI Gateway, observability, eval gate | `gateway/`, `observability/`, `evals/` | — |

## v1 scope — DEMOABLE (minimal new build)
Ingest 2–3 producers over the same codebase; show 7 raw findings collapse to **3 correlated
decisions**; each decision shows real/suppress/needs-human with reason + citations + contributing
producers; one auto-suppress (high bar), one auto-ticket, one routed to human (HITL approve). Reuse the
existing eval harness to report FP-precision/recall on a small labeled set.

## Demo script + "wow"
1. Upload 2 scanner reports (Semgrep + a SARIF from another tool) for the same repo.
2. Plane shows **N→M dedup**: "7 findings → 3 root causes" with the correlation reason.
3. Decision A auto-suppressed (confidence ≥ 0.95) with audited reason; Decision B auto-ticketed;
   Decision C → **needs-human** → approve in one click (HITL).
4. Open any decision → full **"why"** (citations, contributing producers, policy hits, reasonCode).
5. Metrics: duplicate-ticket reduction %, FP precision/recall from eval, MTTR. *"This is the
   AutoTriage/correlation lane, but explainable and governed — and I've built the real version of this
   pipeline at enterprise scale."*

## Success metric
Duplicate-ticket reduction ≥ 50% on the demo set; every suppression has an audited, citation-backed
reason; FP precision/recall reported from the eval harness (not fabricated).

## 5-year evolution
Correlation plane → "trust/triage layer" for any finding producer (security, then observability
alerts, then data-quality alerts) → the verifier/oversight category in the thesis. The dedup +
explainability + audit primitives generalize beyond security.

## Key risk
"Isn't this just your copilot again?" Mitigation: lead with **multi-producer correlation** and the
**explainability plane** framing (a distinct category), and lean on the un-fakeable Ox ASPM story.
