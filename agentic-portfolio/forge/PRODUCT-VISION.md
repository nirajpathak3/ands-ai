# ANDS Forge OS — Autonomous Product-Development Operating System

> Product vision & build plan. Product name: **ANDS Forge OS**. **Two layers:**
> - **Forge kernel** — the generic, domain-agnostic multi-agent engine (supervisor, scheduler, skill
>   packs, HITL, eval, AI gateway, audit). The durable, reusable substrate.
> - **ANDS Forge OS** — the flagship application: it runs the product-development *program* (the
>   lifecycle below) on the kernel.
>
> **Genericity is preserved** because the *program* (blueprint) and *skill packs* are **swappable data** —
> point the same kernel at any project/product by loading a different blueprint + packs. The kernel never
> hardcodes product-development specifics.
>
> Supersedes the earlier "agent factory" one-pager
> [`../visions/forge-orchestration-platform.md`](../visions/forge-orchestration-platform.md) by
> generalizing it into an **autonomous, multi-agent OS that takes a product vision and drives the entire
> product-development lifecycle** — HITL approval at every stage, trainable skills, parallel sub-agents,
> environment-agnostic execution (Cursor / VS Code / Antigravity / CLI / CI).
>
> Status: **vision locked; ready to build.** Repo: `D:\ands-ai\ands-forge-os`. Last updated 2026-06-26.

---

## 1. One-liner & the shift

> **Give Forge a product vision the way you'd brief a CTO/CPO. It autonomously runs the whole
> product-development lifecycle — discovery → strategy → UX → architecture → security → analytics →
> execution → ops-readiness — coordinating a hierarchy of specialized, trainable agents that work in
> parallel, pausing only for human approval at each gate, and emitting real, reviewable artifacts with a
> full audit trail of every decision.**

The earlier Forge was a "factory that writes a vision doc." This is bigger: **an operating system for
building products**. The lifecycle diagram you provided ([`assets/lifecycle-architecture.png`](assets/lifecycle-architecture.png))
is adopted as the OS's default **program** — the artifact dependency graph Forge executes.

## 2. Top-level UX (the CPO/CTO experience)

1. A human in a **CPO/CTO/VP** role states a product vision (a paragraph, a doc, or a chat).
2. A **Vision Intake** agent clarifies it into a structured **Vision Brief** (problem, audience,
   success metrics, constraints, non-goals) and gets it **approved** (gate #1).
3. The **Supervisor** ("the OS kernel") compiles the lifecycle blueprint into a concrete, ordered plan,
   shows it, and gets it **approved**.
4. From there it **runs autonomously**: it auto-assigns stage-leads and sub-agents, runs independent
   work **in parallel**, self-reviews each artifact, and **pauses at each stage gate for HITL approval**
   (approve / reject-with-feedback / edit). The human never has to "call" an agent.
5. Output: a complete, versioned artifact set (PRD, personas, flows, **mockups**, domain model, system
   architecture, API/DB specs, ADRs, threat model, analytics plan, roadmap/backlog, runbooks, PRR…) —
   each with the reasoning, citations, cost, and approval history behind it.

## 3. Core concepts (the "OS" model)

| OS concept | What it is | Reuse from `ai-secops-copilot` |
|---|---|---|
| **Kernel / Supervisor** | Owns the vision, compiles the plan, schedules agents, enforces gates, manages HITL, budget, and global state | `graph/build.py` + `graph/runner.py` (compiled StateGraph + checkpointer) |
| **Program = Lifecycle Blueprint** | A declarative DAG of stages → artifacts → owning agent role → edge type (gate vs informs) → quality bar. Swappable per product type → **genericity** | new (data-driven; not hardcoded roster) |
| **Processes = Agents** | A 3-tier org (executive → stage-leads → worker sub-agents) + cross-cutting reviewers | `graph/nodes.py` node + DI seam pattern |
| **Scheduler** | Topological resolver that runs all *ready* nodes in **parallel** up to a concurrency/budget limit | new (over LangGraph) |
| **Skills = Skill Packs** | Per-role, versioned, **trainable** capability bundles (prompt+policy, exemplars, corpus, schema, tools, eval rubric, quality bar) | `prompts.py`, `schemas.py`, `rag/`, `evals/` |
| **Memory / Blackboard** | Durable run state: vision, plan, artifacts, critiques, approvals, cost, traces + long-horizon project memory (pgvector) | `graph/state.py`, persistence seam, pgvector |
| **Syscalls = Tools** | Everything an agent can *do*, behind a `Tool` port (web_search, rag_search, write_file, scaffold_repo, render_mockup, run_eval, diagram) | ports & adapters in `providers/`, `rag/` |
| **Drivers = Environment adapters** | How Forge plugs into Cursor / VS Code / Antigravity / CLI / CI (via **MCP server** + REST + CLI) | new (gateway/auth patterns reused) |
| **Governor** | Confidence/materiality gates, policy-as-code, cost/time budgets, eval-as-gate, audit | `governance.py`, `policy.py`, `gateway/`, `evals/`, `AuditRecord` |

## 4. The agent org chart (hierarchical, auto-assigned)

**Tier 0 — Executive**
- **Vision Intake & Steward** — elicits/clarifies the vision; guards scope and acceptance criteria.
- **Supervisor / Planner (the kernel)** — decomposes vision → plan over the blueprint; schedules; enforces gates, budget, HITL; owns the blackboard.

**Tier 1 — Stage leads** (one per lifecycle stage; each plans + coordinates its sub-agents)
- Discovery lead · Strategy/PM lead · UX lead · Architecture lead · Security lead · Analytics lead · Delivery lead · Ops-readiness lead.

**Tier 2 — Worker sub-agents** (per artifact; run in parallel where independent)
- *Discovery:* user-research · competitive-analysis · business-case.
- *Strategy:* PRD author · AI-capability-mapper.
- *UX:* persona · user-flow · **wireframe/mockup** (emits previewable mockups + flows for approval).
- *Technical:* domain-modeler · system-architect · API-spec · DB-schema · ADR · feature-TDD · **dev/scaffold** (codegen).
- *Security:* security-reqs · RBAC-matrix · threat-model · compliance.
- *Analytics:* event-model · analytics-plan · DWH/data-model.
- *Execution:* roadmap · DoR/DoD · epic-backlog · dependency-matrix · QA-plan.
- *Ops:* monitoring · alerting · runbooks · DR-plan · PRR/launch-gate.

**Cross-cutting (mandatory, every stage)**
- **Reasoner/Thinker** — not a separate agent but a required *reason→plan→act→reflect* loop inside every
  agent (with the chain logged for audit).
- **Critic/Reviewer** — scores each artifact against its rubric (quality gate).
- **Red-team / Devil's-advocate** — adversarial review (risks, gaps, hidden assumptions) before a human
  ever sees it — this is the "development review and all mandatory agents" you asked for.

## 5. The lifecycle as the OS program (your diagram, improved)

Forge executes your lifecycle graph. Edge types from your legend are first-class: **solid = gate (must
precede)**, **dotted = informs (non-blocking context)**. Improvements I made (see §10) include
shift-left parallelism for Security/Analytics and explicit feedback loops.

```mermaid
flowchart TB
    V[Vision Brief\n(approved)] --> SUP[Supervisor / Kernel\ncompile plan]
    SUP --> G0{HITL: approve plan}
    G0 -->|approved| DISC

    subgraph DISC[Discovery ∥]
        UR[user research]; CA[competitive analysis]; BC[business case]
    end
    DISC --> GD{HITL gate}
    GD --> STR
    subgraph STR[Strategy]
        PRD[PRD]; ACM[AI capability map]
    end
    STR --> GS{HITL gate}
    GS --> UX
    subgraph UX[UX ∥]
        PER[personas]; FLW[user flows]; WF[wireframes + mockups]
    end
    UX --> GU{HITL gate}
    GU --> TEC

    subgraph TEC[Technical ∥]
        DM[domain model]; SA[system architecture]; API[API specs]; DB[DB schema]; ADR[ADRs]; TDD[feature TDDs]
    end
    %% shift-left: security & analytics start from architecture draft (informs), not strictly after
    SA -.informs.-> SEC
    SA -.informs.-> ANA
    TEC --> GT{HITL gate}
    GT --> SEC & ANA

    subgraph SEC[Security ∥]
        SR[security reqs]; RBAC[RBAC matrix]; TM[threat model]; CR[compliance reqs]
    end
    subgraph ANA[Analytics ∥]
        EM[event model]; AP[analytics plan]; DWH[data model / DWH]
    end
    SEC & ANA --> GSA{HITL gate}
    GSA --> EXE
    subgraph EXE[Execution ∥]
        RM[roadmap]; DOD[DoR/DoD]; EB[epic backlog]; DEP[dep matrix]; QA[QA plan]
    end
    EXE --> GE{HITL gate}
    GE --> OPS
    subgraph OPS[Ops readiness ∥]
        MON[monitoring]; AL[alerting]; RB[runbooks]; DR[DR plan]; PRR[PRR / launch gate]
    end
    OPS --> GO{HITL: launch gate}

    %% feedback loops: a rejection routes back with feedback (bounded)
    GD -.reject+feedback.-> DISC
    GU -.reject+feedback.-> UX
    GSA -.security finding reopens.-> TEC

    %% cross-cutting substrate
    SUP --- GW[AI Gateway: route/fallback/cache/cost]
    SUP --- EVAL[eval-as-gate + critic + red-team]
    SUP --- OBS[audit + traces + cost]
    SUP --- MEM[(blackboard + project memory)]
```

## 6. Autonomy + HITL (how they coexist)

- **Default: a HITL gate at the end of every stage.** Forge runs autonomously *between* gates and
  **pauses (durable `interrupt`/checkpoint)** at each gate; the human approves / rejects-with-feedback /
  edits, then it resumes (`Command(resume=...)`) — across sessions, by `thread_id`.
- **Materiality dial:** each gate has a configurable mode — `always-human`, `auto-if-eval≥bar`, or
  `auto`. So you can let low-risk stages flow and force humans on high-stakes ones. This is what makes it
  feel autonomous without losing control.
- **Bounded feedback loops:** a rejection re-opens the producing stage with the human's notes (capped
  iterations); some rejections **cascade** (e.g., a threat-model finding re-opens Technical).
- Every gate decision, critique, and revision is an **append-only audit event** with a `reasonCode`.

## 7. Trainable skills (skill packs)

A **skill pack** makes an agent role better/domain-specialized **without changing the kernel**:

```
SkillPack = {
  role: "system-architect",
  policy: <system prompt + guardrails>,
  exemplars: [few-shot gold artifacts],
  corpus: <retrieval sources + citations>,        # RAG
  output_schema: <Pydantic contract>,             # structured output
  tools: [allowed Tool ports],
  rubric: <eval criteria + quality bar>,          # judged by Critic
  version, eval_score
}
```

"Training" = **author → evaluate (LLM-as-judge vs. rubric) → version → hot-load** packs (optional
fine-tune later). The same Forge produces a fintech PRD or a healthcare PRD by swapping packs. This is
also the bridge to **Project 3 (trainable domain-expert)** — same mechanism.

## 8. Parallel execution

The scheduler computes a topological order over the blueprint and runs **all ready nodes concurrently**
(e.g., the 3 Discovery agents at once; API-spec ∥ DB-schema after domain-model), bounded by a
concurrency limit and a **cost/time budget governor** that can pause/escalate. LangGraph handles the
graph; the parallel fan-out + budget governor is the net-new orchestration.

## 9. Environment-agnostic (Cursor / VS Code / Antigravity / CLI / CI)

Forge's core is a **headless service**; environments are just clients. Three interfaces:
- **MCP server** — the primary integration. Cursor, VS Code, and Antigravity are MCP/agent clients, so
  exposing Forge as MCP tools (`forge.start_run`, `forge.approve`, `forge.status`, `forge.get_artifact`)
  lets any of them drive and observe runs natively.
- **REST API + Web dashboard** — for non-IDE use, the run timeline, approvals, mockup previews, traces.
- **CLI** — for scripting and CI gates.
Artifacts land on the **filesystem/Git** via the `write_file`/`scaffold_repo` ports, so the output shows
up in whatever editor the user already has open. (The orchestration logic stays identical across all.)

## 10. Improvements I made to your architecture

1. **Vision-intake stage added** before Discovery (structured Vision Brief + acceptance criteria) — your
   diagram starts at "Product vision" with no elicitation/approval step.
2. **Gates and "informs" made executable** (your dotted/solid legend → typed DAG edges the scheduler
   honors).
3. **Shift-left parallelism:** Security & Analytics begin from the *architecture draft* (informs), not
   strictly after all Technical artifacts — closer to real practice and faster.
4. **Explicit feedback/cascade loops:** rejections route back with feedback; some (e.g., security)
   re-open upstream stages. Your diagram is forward-only; real lifecycles iterate.
5. **Mandatory cross-cutting reviewers** (Critic + Red-team) at *every* stage, not just at the end.
6. **Machine-checkable DoR/DoD** = per-artifact eval rubrics, so "autonomous" stays safe.
7. **Budget/feasibility governor** (cost/time caps with escalation) — absent from the diagram, essential
   for autonomy.
8. **Environment-agnostic interface layer (MCP/REST/CLI)** — so it runs in Cursor/VS Code/Antigravity.
9. **Skill-pack abstraction** so the same OS is generic across product types and **trainable**.

## 11. Reuse mapping (substrate from `ai-secops-copilot`)
AI Gateway (routing/fallback/cache/cost), governance + policy + `reasonCode`, durable HITL
(interrupt/checkpoint/resume), eval harness + LLM-as-judge + regression gate, observability
(traces/metrics), guardrails (Pydantic + prompt-injection isolation), append-only audit + CQRS read
models, persistence seam + pgvector, multi-tenancy/auth. **~75–80% of the kernel already exists**; the
net-new is the blueprint/scheduler/agent-org/skill-pack/mockup/MCP layer.

## 12. MVP — a demoable vertical slice (be ruthless)

The full lifecycle OS is the **5-year vision**, not the first build. **v1 (demoable in ~1 week)** proves
the OS shape on a *thin but end-to-end* slice:

- **In:** Vision Intake → **plan approval (HITL)** → Discovery (1–2 parallel agents) → PRD → UX
  (personas + flows + **one real mockup** rendered as HTML) → System architecture + API/DB sketch →
  **scaffolded repo** (folders, README, FastAPI skeleton, eval stub). **HITL gate at each stage**
  (materiality dial defaulting most to auto, 2–3 to human). Critic + red-team review. Parallel fan-out
  in ≥1 stage. AI Gateway + traces + cost + audit. Eval-as-gate + CI. Offline deterministic mode. One
  environment client (CLI + web dashboard; **MCP** if time permits).
- **Cut / defer:** full Security/Analytics/Ops stages (stub as auto-pass with placeholder artifacts),
  dynamic agent spawning, real code *execution*/sandbox, fine-tuning, multi-tenant UI, all IDE adapters
  (ship MCP first, others later).
- **Killer demo flow:** vision in → approve plan → watch parallel agents → approve PRD → approve a
  rendered **mockup** → a **real scaffolded product repo** appears on disk, every step audited with cost
  + traces. Close: *"this is the OS I'll build the rest of my portfolio with."*

## 13. Build sequence (for the new development chat)
1. Extract `core` kernel from the copilot (gateway/governance/HITL/eval/observability) → walking
   skeleton runs offline.
2. Define `Blueprint` (the lifecycle DAG) + `RunState` blackboard + `SkillPack` schema (data-driven).
3. Supervisor + scheduler (topological, parallel, budget governor) with deterministic stub agents
   end-to-end.
4. Real agents via skill packs + AI Gateway (structured output, bounded reprompt); Critic + red-team.
5. HITL gates (interrupt/resume) with the materiality dial; feedback loops.
6. Tools: rag_search, web_search (real+stub), write_file, scaffold_repo, **render_mockup**, run_eval.
7. Eval-as-gate + CI; per-agent traces + cost; web dashboard (timeline, approvals, mockup preview).
8. MCP server interface; then polish + record demo.

## 14. Success metrics
Vision in → approved, eval-passing artifact set + scaffolded repo out, with a full audit + cost trace of
every agent decision; ≥1 stage runs agents in parallel; HITL approve/reject/resume works across
sessions; eval regression gate green in CI; runs offline-deterministic for demos.

## 15. Risks & mitigations
- **Boil-the-ocean / "another framework"** → ship the v1 vertical slice; stub later stages; differentiate
  on *governed + evaluated + observable + autonomous-with-HITL*, never on primitives.
- **Demo fragility (LLM non-determinism)** → deterministic offline mode; eval gate; bounded loops.
- **Context explosion across many agents/artifacts** → blackboard + project memory + per-stage context
  scoping (only pass artifacts on incoming DAG edges).
- **Parallelism bugs / runaway cost** → concurrency limit + budget governor + idempotent nodes.

## 16. Decisions & open items
- **DECIDED — name = ANDS Forge OS** (kernel layer = "Forge kernel"); repo = `D:\ands-ai\ands-forge-os`.
- Open — v1 environment client: **MCP-first** vs web-dashboard-first.
- Open — mockup rendering for v1: HTML/React preview vs. image-gen vs. wireframe spec.
- Open — materiality defaults: which v1 stages are `always-human` vs `auto-if-eval≥bar`.
