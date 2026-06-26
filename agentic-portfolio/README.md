# Agentic AI Portfolio — strategy hub

> Cross-product strategy, research, backlog, roadmap, and product visions for my agentic-AI work.
> Deliberately kept **separate** from the `ai-secops-copilot` product repo. The copilot is one product
> (and the reusable substrate); this folder is the *portfolio* that decides what to build next and why.
>
> Last updated: 2026-06-26.

---

## The one-paragraph thesis

Models are getting commoditized; **trust is not**. Every domain I investigated (security, finance,
insurance, pharma, healthcare, education, labs) is flooded with shallow AI (chatbots/copilots) and
starved of **governed autonomous operators** — multi-step, stateful, tool-using systems with
HITL-by-materiality, eval-as-a-gate, audit/accountability, and cost control. That governed-automation
**substrate** is exactly what I already built in `ai-secops-copilot`, and it is the scarce, compounding
asset. So my bet is: **build the substrate (and the factory that ships it), then point it at wedges
where the audit burden is highest or where I have an unfair edge.** Not another worker agent — the
*manager/oversight* layer, and vertical operators built on top of it.

## Two-layer plan

- **Layer 1 — IT base (build now):** the flagship orchestrator + a companion, both reusing my stack.
  Establishes the *AI platform engineer* identity and the **factory** I build everything else with.
- **Layer 2 — beyond IT (future, build via the factory):** governed vertical operators in
  underexploited, audit-heavy domains (life-sciences lab/research ops, special-ed/IEP, education ops),
  where domain incumbents can't build autonomous systems themselves.

## Status board

| # | Project | Layer | Status | Doc |
|---|---------|-------|--------|-----|
| 1 | **ANDS Forge OS** — autonomous product-dev OS (FLAGSHIP) · _Forge kernel_ underneath | IT | **Decided — build 1st; vision locked** | [**plan**](forge/PRODUCT-VISION.md) |
| 2 | **ANDS Sentinel** — agent red-team & guardrail verifier (companion) | IT | **Decided — scope locked** | [**scope**](verifier/SCOPE.md) · [one-pager](visions/agent-security-verifier.md) |
| 3 | **Trainable domain-expert** (expertise-as-software) | IT | Decided — build later via Forge | [vision](visions/trainable-expert.md) |
| — | Oversight/governance plane | IT | Tier-1 future (or Forge wedge) | [vision](visions/oversight-governance-plane.md) |
| — | Agent identity / authz | IT | Tier-1 future (deep moat) | [vision](visions/agent-identity-authz.md) |
| — | Change-risk / release gate | IT | Project-2 alternative | [vision](visions/change-risk-release-gate.md) |
| — | Triage/correlation plane | IT | Demo-only (commodity product) | [vision](visions/triage-correlation-plane.md) |
| — | Compliance-evidence agent | IT | Tier-2 | [vision](visions/compliance-evidence-agent.md) |
| — | FinOps remediation agent | IT | Tier-2 | [vision](visions/finops-remediation-agent.md) |
| L2 | Life-sciences lab/research ops | non-IT | Future — top pick | _stub in BACKLOG_ |
| L2 | Special-ed / IEP ops | non-IT | Future | _stub in BACKLOG_ |
| L2 | Education operations | non-IT | Future | _stub in BACKLOG_ |

### Project 2 — the open decision
Recommended: **Agent-security verifier** (companion to Forge: "I build agents *and* prove they hold").
Alternatives: **Change-risk/release gate** (release-eng flavor, offline-demoable) or **Triage plane**
(zero-build, max reuse, but commodity). See [`ROADMAP.md`](ROADMAP.md#project-2) for the trade-offs.

## How to navigate

- [`ROADMAP.md`](ROADMAP.md) — **final IT suggestions + the build roadmap** (start here).
- [`BACKLOG.md`](BACKLOG.md) — every candidate, scored and ranked (IT + non-IT), corrected for 2026.
- [`research/MARKET-RESEARCH-2026.md`](research/MARKET-RESEARCH-2026.md) — verified competitive/demand
  findings with sources (the evidence behind the scores).
- [`DECISIONS.md`](DECISIONS.md) — decision log, the selection lens, corrections to earlier analysis,
  the 5-year thesis.
- [`forge/`](forge/) — **flagship build plan**: the autonomous product-development OS (vision +
  architecture + MVP + build sequence), with the lifecycle diagram in `forge/assets/`.
- [`visions/`](visions/) — one-page product visions per idea (Forge's older one-pager lives here,
  superseded by `forge/PRODUCT-VISION.md`).
- [`career/`](career/) — resume / interview / cover-letter prep (moved out of the copilot repo).
- [`archive/`](archive/) — prior-session artifacts kept for history.

## Conventions
- This folder is the **source of truth** for portfolio strategy. Individual vision docs may carry older
  priority labels in their body; the **status board above + BACKLOG + ROADMAP win** on current priority.
- The `ai-secops-copilot/` repo stays focused on the copilot product (its `PRODUCT_VISION`,
  `SYSTEM_DESIGN`, ADRs). Nothing here merges into it.
