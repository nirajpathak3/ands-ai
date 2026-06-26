# Backlog #2 — Agent-security red-team & guardrail-verification harness

> **STATUS (2026-06-26): DECIDED as Project 2 — scope locked.** Finalized, build-ready scope (grounded
> in the real Forge OS attack surface, with a `Target` adapter to test against `ands-forge-os`) lives in
> [`../verifier/SCOPE.md`](../verifier/SCOPE.md). This page is the original one-pager, kept for history.
>
> Re-scoped to the open *agentic* gap (tool-use abuse, multi-agent pipelines, indirect/RAG injection,
> your-own-agents-in-CI). Correction: the field is **consolidating, not "wide open"** (Promptfoo→OpenAI,
> Lakera→Check Point) — see [`../research/MARKET-RESEARCH-2026.md`](../research/MARKET-RESEARCH-2026.md).

> Agentic adversary + verifier that probes *other* agents for prompt injection, tool abuse, data
> exfiltration, and authz bypass, then produces a governed security report. Peers: emerging (Lakera,
> Protect AI, Garak) but the **agentic, eval-gated, CI-integrated** verifier for *your own* agents is
> wide open. One-line: *a CI-grade red-team agent that attacks your agents and proves they hold.*

---

## Problem
Everyone is shipping agents with tool access. Almost no one tests them adversarially. Prompt
injection, tool abuse, exfiltration, and broken authz are the top unsolved agent-security pains — and
they'll matter more every year as agents get more autonomy and more tools. There is no standard,
CI-integrated way to continuously verify an agent's guardrails hold.

## Why agentic
An adversary agent plans attack strategies → executes multi-step injection/abuse attempts via tools →
observes the target agent's behavior → adapts → scores → reports. Stateful, multi-step, tool-using,
decisioning. A static scanner can't adapt its attacks.

## Target user / buyer
AI-platform / security teams shipping agents; the same buyer as the flagship. Buyer = eng leadership
who must ship agents safely (this is the natural companion product to Forge).

## Why my stack fits (reuse ~65%)
- **Prompt-injection isolation knowledge** (`prompts.py` UNTRUSTED/TRUSTED split) → I already
  understand the defense; this inverts it into an attack/verify harness.
- **Eval harness + LLM-as-judge + regression gate** (`evals/`) → the core: attacks are eval cases,
  pass/fail is a gate; *this is the single strongest reuse*.
- **Governance + reasonCode + audit** → every attack result is an audited verdict.
- **AI Gateway** → run adversary + judge models with cost control.
- **Observability** → trace every attack step.
- New: attack library (injection corpus, tool-abuse patterns), target-agent harness/adapter.

## Architecture sketch
Build **via Forge**: Planner (attack plan) → Attacker (executes, fan-out across attack classes) →
Observer (captures target behavior + tool calls) → Judge (scored verdict per attack) → gate (CI
pass/fail) → audited report. Target agent connects behind a `Target` protocol (ports & adapters).

## v1 demo scope
Point it at *my own* secops copilot or Forge as the target; run an injection corpus + a tool-abuse
suite; show 1 caught vulnerability ("finding text tried to override system instructions → blocked by
isolation") and 1 pass; emit a CI gate result + report. Self-referential demo = very memorable.

## Success metric
Attack coverage (classes run), catch rate on seeded-vulnerable target, zero false "safe" on known-bad,
runs as a CI gate in < N minutes.

## 5-year evolution
Red-team harness → continuous agent-security monitoring → the "agent security / verifier" category
(prompt injection, tool abuse, exfil, agent identity/authz). One of the most durable unsolved pains;
strong career-resilience for a platform+security engineer.

## Key risk
Niche today / education needed. Mitigation: bundle as the safety story *for the flagship* ("I build
agents **and** I prove they're safe") — turns a risk into a differentiated narrative.
