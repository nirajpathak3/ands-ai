# Agentic product backlog — scored & ranked (corrected, June 2026)

> Decision-grade backlog. Scores 1–5 (5 = best). "Crowd" inverted (5 = open field, 1 = commoditized) and
> **verified live** — see [`research/MARKET-RESEARCH-2026.md`](research/MARKET-RESEARCH-2026.md). "Reuse"
> = % of my `ai-secops-copilot` stack reusable. Supersedes the prior-session backlog in
> [`archive/BACKLOG-v1-prior-session.md`](archive/BACKLOG-v1-prior-session.md), whose Crowd/Moat scores
> for triage (#0) and agent-security (#2) were over-optimistic.

---

## IT projects

| Idea | Agentic | Crowd (verified) | Moat (my edge) | Effort (5=low) | Reuse | 5-yr | Wow | Verdict |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|
| **Forge — orchestration platform (FLAGSHIP)** | 5 | 3 | 4 | 3 | 80% | 5 | 5 | **Build 1st** |
| **Agent-security verifier** (re-scoped to agentic gap) | 5 | 3 | 4 | 3 | 65% | 5 | 5 | **Recommended Project 2** |
| **Oversight / governance plane** | 5 | 4 | 5 | 3 | 75% | 5 | 4 | Tier-1 (or Forge wedge) |
| **Agent identity / authz** | 4 | 4 | 5 | 2 | 40% | 5 | 3 | Tier-1 (deep moat, later) |
| **Trainable domain-expert** (expertise-as-software) | 4 | 3 | 3 | 3 | 50%→70%* | 4 | 4 | **Project 3 — build via Forge** |
| **Change-risk / release gate** | 5 | 3 | 4 | 3 | 70% | 4 | 4 | Project-2 alternative |
| Triage / correlation plane | 4 | 2 | 2 | 5 | 85% | 3 | 4 | Demo-only / P2 fallback |
| Compliance-evidence agent | 5 | 3 | 4 | 3 | 70% | 5 | 4 | Tier-2 |
| FinOps remediation agent | 5 | 3 | 4 | 3 | 70% | 4 | 4 | Tier-2 |
| Agent eval/observability | 5 | 2 | 3 | 4 | 75% | 5 | 3 | Fold into oversight plane |
| AI incident commander / SRE | 5 | 2 | 3 | 2 | 55% | 4 | 4 | **Drop** (crowded, integ-heavy, overlaps Forge) |
| PR-review agent (Idea B) | 4 | 1 | 2 | 4 | 70% | 2 | 2 | **Skip** (commoditized) |

\* Reuse rises to ~70% once the trainable expert runs as a Forge tenant (skill pack = roster + tools + eval).

## Non-IT projects (Layer-2 — build later via Forge)

Filter applied: agentic-necessity × **low domain AI maturity** × solo-accessible data × audit-intrinsic ×
personal wedge. (See lens in [`DECISIONS.md`](DECISIONS.md).)

| Idea | Agentic | Crowd (verified) | Solo-accessible | Audit-native | Verdict |
|------|:--:|:--:|:--:|:--:|---|
| **Life-sciences lab / research & quality ops** | 5 | 4 | 4 (synthetic protocols) | 5 (GxP) | **Top Layer-2 pick** |
| **Special-ed / IEP operations** | 4 | 4 | 3 (synthetic, FERPA) | 4 (IDEA) | Strong, mission-aligned |
| **Education operations** (advising/at-risk/enrollment) | 4 | 3 | 3 | 3 (FERPA) | Viable (NOT tutoring) |
| Veterinary practice operations | 4 | 4 | 4 | 2 | Greenfield (least competition) |
| Healthcare care-coordination | 5 | 2 | 1 (EHR/HIPAA) | 5 | Skip-as-build (battlefield) |
| Regulated back-office (insurance/finance/PV/DSAR) | 5 | 2 | 1 | 5 | Skip-as-build (no edge); harvest patterns |
| Consumer mental-health / cognition | 4 | 2 | 4 | 2 | **Skip** (crowded + regulated). Use as P3 skill pack |

## Tiers (current)
- **Build/demo now:** Forge + Project 2 (recommended: agent-security verifier).
- **Build later via factory (IT):** trainable-expert (P3), oversight plane, agent identity, compliance, finops.
- **Build later via factory (non-IT Layer-2):** lab/research ops (top), special-ed/IEP, education-ops.
- **Skip:** PR-review, incident-commander-as-P2, triage-as-product, healthcare/back-office-as-solo,
  consumer mental-health.

## Deliberately NOT doing
Generic "agent framework," chatbots, RAG-Q&A apps, anything competing with frontier labs on model depth,
anything where my distribution/domain edge is zero, and "find an empty vertical" bets (there are none).
