# Project 3 — Trainable domain-expert (expertise-as-software)

> DECIDED. Build later, as a Forge tenant. Re-aimed: the moat is **encoded investigative process +
> durable domain memory + verifiable method** — NOT "deeper knowledge than ChatGPT" (that fights the
> frontier labs and loses). One-line: *an agent you train by composable skill packs that encode an
> expert's workflow, memory, and guardrails — and shows an auditable trail of why it reasoned as it did.*

---

## Problem
Generic LLMs are shallow and amnesiac in deep domains: no durable memory of *your* context, no repeatable
investigative method, no audit of their reasoning. Consumers paper over this with chat wrappers. What's
missing is **expertise as composable, evaluated software** — a method you can load, inspect, and trust.

## Why agentic (not a chatbot)
Multi-step investigation with state: intake → hypotheses → targeted probing questions → evidence
gathering (tools/RAG) → differential reasoning → governed disposition (answer / ask-clarifying /
escalate) → durable memory update → audited reasoning trail. A chatbot can't run a staged, stateful,
self-correcting investigation with memory and an audit log.

## What a "skill pack" is (concrete, composable)
`{ retrieval corpus + citations · a staged investigative workflow (graph of steps) · domain Pydantic
schemas · an eval set (gold transcripts judged by rubric) · guardrails + escalation rules · a memory
schema }`. "Trainable" = compose/evaluate new packs, not fine-tune a base model. Examples: AppSec-
assessment pack, my own brainstorm/analysis pack, a (carefully-scoped, non-clinical) psychology-
*exploration* pack, a neuroscience-investigation pack.

## Target user / buyer
Professionals who need deep, repeatable, auditable investigation in one domain; later, a *marketplace*
of expert packs. (Buyer varies by pack; start with packs where I'm the user — my own analysis pack.)

## Why my stack fits (reuse ~50% → ~70% as a Forge tenant)
- **Governance gate** → answer / ask-clarifying / escalate (relabel the 3-disposition model).
- **RAG seam** → per-pack corpus + citations (`rag/`).
- **Durable HITL** → escalate-to-human on low confidence / safety triggers.
- **Audit trail + reasonCode** → the inspectable reasoning log (the product differentiator).
- **Eval harness + LLM-as-judge** → score open-ended reasoning against expert rubrics (my strength).
- **Forge** → a pack = worker roster + tool registry + eval set loaded at runtime.
- New: long-horizon **domain memory** (pgvector + summarization + a "what I know about this case" store),
  pack format/loader, rubric judges per pack.

## Architecture sketch
Runs on **Forge**. Load a skill pack → supervisor follows the pack's staged workflow → workers
investigate (RAG + tools) → critic/eval scores against the pack rubric → governance decides answer vs.
ask vs. escalate → memory store updated → audited reasoning trail rendered. Swap the pack → same engine,
different expertise.

## v1 demo (offline)
Load my own "brainstorm/analysis" pack; point it at a backlog idea; it runs a **structured
investigation** (decompose → probe → hypotheses → evidence → conclusion) with **citations + an audit
trail of its reasoning steps**; then swap to a second pack and show the same engine go deep in another
domain. "Same engine, loadable expertise, inspectable method."

## Hard problems
- **Long-horizon memory** across sessions (what's known about this case/domain).
- **Evaluating open-ended reasoning** (rubric-based LLM-as-judge).
- **Knowing when NOT to answer** (the safety/escalation gate is the product — essential for any
  psychology/health-adjacent pack; position as *exploration/analysis support*, never diagnosis).

## Success metric
On a held-out set per pack: investigative-quality rubric score beats a vanilla-LLM baseline; every
conclusion is citation-backed with an auditable reasoning trail; safety gate correctly escalates seeded
out-of-scope cases.

## 5-year evolution
Single pack → multi-pack engine → marketplace of evaluated expert packs. Durable because the moat is
*process + memory + auditability*, which base models structurally lack.

## Key risk
"Make the LLM deeper" fights the frontier labs. Mitigation: never sell knowledge depth; sell **method +
memory + verifiable, auditable reasoning** on top of whatever base model — and ship it on Forge so reuse
and the governance story carry it.
