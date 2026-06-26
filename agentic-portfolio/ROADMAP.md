# IT projects — final suggestions & roadmap

> Scope: the **Layer-1 IT base** — the two demo projects for the interview (~1–2 weeks out) plus the
> third project built later via the factory. Grounded in the verified research and full reuse of
> `ai-secops-copilot`. Roadmap is milestone-based, not rigid day-by-day.

---

## Final suggestions (committed recommendation)

### Project 1 — Forge (flagship, DECIDED) — build first
A **governed agent runtime / orchestration platform**: give it a goal → supervisor plans → worker roster
(researcher/architect/author/critic) executes with tools → critic-gated revise loop → HITL approvals →
emits a real artifact, with per-agent traces, cost, and an eval gate. Positioned as *the part
LangGraph/CrewAI leave out: governed + evaluated + observable*. It is also the **factory** that scaffolds
every later product. ~80% reuse. Full plan: [`visions/forge-orchestration-platform.md`](visions/forge-orchestration-platform.md).

### Project 2 — RECOMMENDED: Agent-security verifier (re-scoped) {#project-2}
A **CI-grade red-team + verifier that attacks your *own* agents** — agentic tool-use abuse, multi-agent
pipeline manipulation, indirect/RAG injection — and emits a governed pass/fail report. Why this over the
alternatives:

- **Differentiates from Forge.** Forge = *build agents*; verifier = *prove they hold*. Two demos, one
  story ("I build agents **and** I make them safe"), but visibly different — avoids the trap of two
  demos that both look like "an agent governance platform."
- **Rides the one security niche still *growing*, not commoditizing** (Promptfoo→OpenAI,
  Lakera→Check Point), and the open sliver (agentic tool-use, multi-agent, your-own-agents-in-CI) is
  exactly where incumbents are weak.
- **Self-referential demo wow:** point it at the copilot/Forge you *just* demoed and catch a real
  injection live.
- **Identity:** positions me as *AI-platform security*, not *AppSec engineer using AI*.
- Reuse ~65% (eval harness + governance + gateway + observability; new = attack library + target adapter).

**Alternatives (swap-in, your call):**
- **Change-risk / release gate** — pick if you want a release-engineering flavor and a fully offline,
  repo+history demo. AppSec+platform fit, ~70% reuse, but emerging-crowded (Koalr/DeployWhisper/PRism).
  [`visions/change-risk-release-gate.md`](visions/change-risk-release-gate.md).
- **Triage / correlation plane** — pick **only** if time is the sole constraint: ~85% reuse, near-zero
  new build, unfakeable Ox story — but it's a commodity ASPM feature, so frame it explicitly as a *demo*,
  not a product. [`visions/triage-correlation-plane.md`](visions/triage-correlation-plane.md).
- **Oversight/governance plane** — most durable, but **overlaps Forge** too much to be a strong *second*
  demo; better as a later product. [`visions/oversight-governance-plane.md`](visions/oversight-governance-plane.md).

> Decision still yours. Default path below assumes Project 2 = agent-security verifier; the roadmap is
> nearly identical for change-risk (swap the worker roster + corpus).

### Project 3 — Trainable domain-expert (DECIDED) — build later via Forge
Expertise-as-software: composable **skill packs** that encode an expert's *investigative workflow +
memory + verifiable method* (not raw knowledge). Runs as a Forge tenant. Build after the interview.
[`visions/trainable-expert.md`](visions/trainable-expert.md).

---

## The reuse spine (do this once, both demos benefit)
Extract a domain-agnostic **`core`** from the copilot — AI Gateway (route/fallback/cache/cost),
governance (confidence/materiality gate + `reasonCode`), durable HITL (interrupt/checkpoint/resume),
eval harness (LLM-as-judge + regression gate), observability (traces/metrics), guardrails (Pydantic +
prompt-injection isolation). Forge and the verifier both sit on this. This is the single highest-leverage
move — it turns "two projects" into "one substrate + two thin heads."

---

## Roadmap — 2-week sprint to the interview

Two tracks depending on your appetite/time. Both prioritize **Forge** (flagship + factory) first.

### Ambitious path (two strong, distinct demos)
- **Day 0 (½ day):** carve out `core` from the copilot (the reuse spine above). Walking skeleton runs
  offline/deterministic.
- **Days 1–6 — Forge v1** (follow its vision's 7-day plan): supervisor + 4 workers, role-aware gateway
  routing, structured outputs, 2 HITL checkpoints, critic-gated revise loop, 4 tools, eval gate, agent
  timeline dashboard. **Killer flow:** goal → approved, eval-passing artifact (a `.md`) on disk.
- **Days 7–11 — Project 2 (verifier) via Forge:** attack-planner → attacker (fan-out over attack
  classes) → observer → judge → CI gate → audited report; target behind a `Target` protocol; point it at
  the copilot. Reuse eval+governance+gateway+observability.
- **Days 12–13 — Harden + assets:** polish both dashboards, write the two one-pagers you'll show, seed
  data, record two demo videos.
- **Day 14 — Rehearse** both demos end-to-end; dry-run the meta-close ("the verifier just attacked the
  agent Forge built; the doc Forge wrote is one item in my backlog — this is the factory").

### Safe path (de-risked, if the fortnight gets tight)
- Days 0–7: **Forge v1** (same as above) — this alone is a flagship-grade demo.
- Days 8–11: **Project 2 = triage/correlation plane** (near-zero new build, ~85% reuse) as the reliable
  second demo; framed honestly as "the AutoTriage/correlation pipeline I know from Ox, made explainable
  and governed."
- Days 12–14: harden, one-pagers, record, rehearse.

> Trigger to fall back: if Forge isn't demo-stable by ~Day 7, take the safe path for Project 2.

### Demo-day narrative (both paths)
1. **Forge** — goal in → plan (approve) → workers + parallel research with citations → critic
   0.62→0.91 self-correct → approve → artifact on disk → dashboard (traces, cost $0.0x, model routing).
2. **Project 2** — (verifier) attack my own agent, catch an injection, CI gate red→green; or (triage)
   7 findings → 3 governed decisions, one auto-suppressed with audited reason.
3. **Close** — "models get commoditized; trust doesn't. I build the governed substrate — and the factory
   that ships it." Show the backlog: Project 3 + the non-IT operators are next, built *with Forge*.

---

## Post-interview roadmap (Layer-1 → Layer-2)
- **Weeks 3–5:** Project 3 (trainable-expert) as a Forge tenant — one skill pack end-to-end (e.g. an
  AppSec-assessment or my own brainstorm/analysis pack) with domain memory + audit trail.
- **Weeks 6–10:** harden `core` into a reusable kernel; optionally stand up the **oversight/governance
  plane** as Forge's commercial wedge, and prototype **agent identity/authz** (the deep moat).
- **Quarter 2+:** Layer-2 — point Forge at the top non-IT wedge (**life-sciences lab/research ops**),
  then special-ed/IEP or education-ops. Each = skill pack + governed operator the domain can't build
  itself. Write full future-vision docs under `visions/future/` when starting each.

---

## Risks & mitigations
- **Scope creep into "another framework"** (Forge) → fixed roster, one demo flow, ruthless v1 cut list;
  differentiate on governed+evaluated+observable, never on primitives.
- **Two overlapping demos** → that's why Project 2 ≠ oversight plane; keep the verifier/triage visibly
  distinct from Forge.
- **Time risk** → the safe path; Forge alone is a sufficient flagship if Project 2 slips.
- **Demo fragility** (LLM non-determinism on stage) → run everything in the copilot's deterministic
  offline mode; eval gate + bounded revise loop with hard caps.
