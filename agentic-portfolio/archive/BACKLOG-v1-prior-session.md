# Agentic product backlog — investigated, scored, ranked

> Decision-grade backlog for: pick 2 demos now, build the rest later via the flagship factory.
> Scoring is 1–5 (5 = best). "Reuse" = % of my existing `ai-secops-copilot` stack I can reuse.
> "Crowd" is inverted in the total (5 = open field, 1 = crowded/commoditized). Be honest: weak ones
> are flagged.

---

## Scoring table

| # | Idea | Agentic? | Demand | Crowd (5=open) | Moat (my edge) | Low effort | Reuse % | 5-yr durable | Career | Wow | **Total** |
|---|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A | **Forge — multi-agent orchestration platform (FLAGSHIP)** | 5 | 5 | 3 | 4 | 3 | 80% / 4 | 5 | 5 | 5 | **43** |
| 0 | **Triage & correlation plane (SECONDARY)** | 4 | 4 | 4 | 5 | 5 | 85% / 5 | 4 | 4 | 4 | **43** |
| 1 | Compliance-evidence / continuous-control agent | 5 | 5 | 4 | 4 | 3 | 70% / 4 | 5 | 4 | 4 | **42** |
| 2 | Agent-security red-team / verifier harness | 5 | 4 | 5 | 4 | 3 | 65% / 4 | 5 | 5 | 5 | **44** |
| 3 | Cloud FinOps remediation agent | 5 | 4 | 4 | 4 | 3 | 70% / 4 | 4 | 4 | 4 | **40** |
| 4 | Incident-response / on-call SRE copilot | 5 | 4 | 2 | 3 | 3 | 60% / 3 | 4 | 4 | 4 | **34** |
| 5 | Vendor / third-party risk (TPRM) agent | 4 | 4 | 4 | 4 | 4 | 65% / 4 | 4 | 3 | 3 | **37** |
| 6 | Data-pipeline / data-quality remediation agent | 5 | 4 | 3 | 3 | 3 | 55% / 3 | 5 | 4 | 3 | **36** |
| 7 | Security-aware dev-loop / PR-review agent (Idea B) | 4 | 4 | 1 | 3 | 4 | 70% / 4 | 3 | 3 | 3 | **32** |
| 8 | Skill-trainable domain-expert agent (Idea C) | 4 | 3 | 3 | 2 | 3 | 50% / 2 | 3 | 3 | 4 | **30** |
| 9 | Agent eval / observability platform | 5 | 4 | 2 | 3 | 3 | 75% / 4 | 5 | 4 | 3 | **35** |
| 10 | Contract / procurement review agent (legal ops) | 4 | 4 | 2 | 2 | 3 | 45% / 2 | 4 | 2 | 3 | **28** |
| 11 | Healthcare prior-auth / claims agent | 5 | 5 | 3 | 2 | 1 | 40% / 2 | 5 | 3 | 4 | **30** |

> Totals sum the numeric columns (reuse counted as its 1–5 score, not the %). Treat ±2 as noise; the
> tiers below matter more than exact ranks.

## Ranking & honest verdict

**Tier 1 — build/demo now (top 4):**
- **A. Forge (flagship)** and **0. Triage/correlation plane (secondary)** — the two demos. A is the
  platform story + build multiplier; 0 is max reuse + an un-fakeable Ox moat.
- **2. Agent-security red-team** — highest total. Open field, durable, and the perfect *companion*
  narrative to the flagship ("I build agents and prove they're safe"). Build third.
- **1. Compliance-evidence agent** — biggest real-money market with strong reuse; build fourth.

**Tier 2 — strong, build later via the factory:**
- **3. FinOps remediation** — clean ROI + platform-engineer credibility; real execution risk.
- **5. TPRM agent** — underserved back-office; good reuse; lower wow.
- **6. Data-quality remediation** — very durable, but weaker reuse and a noisier domain.
- **9. Agent eval/observability** — durable category but crowded (Langfuse/Braintrust/Arize); better
  as a *feature* of Forge than a standalone bet.

**Tier 3 — weak / crowded / skip (be honest):**
- **7. PR-review agent (Idea B)** — *commoditized*. CodeRabbit, GitHub Copilot, Snyk, Greptile already
  own in-PR review. Heavy reuse but low differentiation and low durability. **This is why I picked #0
  over B for the secondary.**
- **8. Skill-trainable domain expert (Idea C)** — interesting but fuzzy buyer, weak moat, and "make
  the LLM deeper" fights the frontier labs head-on. Better expressed as *skill packs inside Forge*
  than a product. Keep as a Forge capability, not a standalone.
- **10. Contract review** — crowded legal-AI space, outside my domain edge.
- **11. Healthcare prior-auth** — huge durable pain but regulatory/data-access moat works *against* a
  solo builder; no domain edge. High-value, wrong builder right now.

## What I'm deliberately NOT doing
Generic "AI agent framework," chatbots, RAG-Q&A apps, anything that competes directly with frontier
labs on model depth, and anything where my distribution/domain edge is zero.

---

## 5-year thesis (summary — full reasoning in chat)

**Trajectory:** override (assistive, human-in-loop) → augment (agent does the work, human approves) →
replace (autonomous within bounded domains, human oversees exceptions). ~Now–2yr: augment for
narrow, well-evaluated tasks. ~2–4yr: bounded autonomy in back-office/ops with audit + oversight.
~4–5yr: agent-to-agent systems where the scarce human role is *oversight of fewer, higher-stakes
decisions*.

**Most exposed roles:** L1 triage, manual QA, first-draft analysts, ticket-pushers, routine ops.
**Least exposed / compounding:** people who build the *substrate* agents run on — orchestration,
governance, eval, observability, security, identity. **That's me.**

**Durable product categories:** autonomous operators (bounded), **oversight/verifier layers**, agent
supervisors/orchestrators, **trust/audit infra**, agent identity/authz, **eval + observability for
agents**, agent-to-agent coordination. My stack already embodies the middle three.

**Unsolved pains worth building around (all in my wheelhouse):** trust/verification/hallucination
accountability; explainability + audit under regulation; eval at scale + drift/non-determinism;
cost/latency/reliability; long-horizon memory/state; **agent security** (prompt injection, tool abuse,
exfil, authz, identity); human-oversight UX for fewer-but-higher-stakes decisions; integration glue;
data quality; liability.

**Where a platform engineer's edge compounds:** governance, reliability, cost control, observability,
and security *are* the moat — these are unglamorous, hard, and exactly what agentic systems lack. They
compound because every new agent needs them and they don't get commoditized by a better base model.

**Contrarian take — fades vs. endures:**
- *Fades:* single-agent "chat with X" wrappers; agent frameworks competing on primitives; demos with
  no eval/observability; "autonomy" marketing without governance; vertical copilots that are thin
  prompt layers over a frontier model.
- *Endures:* the **oversight/verifier/trust** layer, governed orchestration, eval-as-a-gate, agent
  security, and audit/accountability infra. Determinism, governance, and proof-of-correctness win as
  autonomy rises — not bigger models.

**Single best long-term bet:** the **governed orchestration + oversight/verifier plane for agents** —
i.e., Forge (orchestration) + the agent-security/verifier harness (#2) + the triage/correlation/audit
primitives (#0). All three are the same thesis from different angles, and all three are already 60–85%
built in my stack.
