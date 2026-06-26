# ANDS Sentinel — Agent Red-Team & Guardrail Verifier (FINALIZED SCOPE)

> **Project 2 (companion to ANDS Forge OS).** Re-scoped to the open *agentic* gap: tool-use abuse,
> multi-agent pipeline poisoning, indirect/RAG injection, and **agent-governance bypass** — run as a
> **CI-grade verifier that attacks your own agents**. Primary target: **ANDS Forge OS** (self-referential
> demo). Supersedes the one-pager [`../visions/agent-security-verifier.md`](../visions/agent-security-verifier.md).
>
> Status: **scope locked; ready to build.** Proposed repo: `D:\ands-ai\ands-agent-verifier`.
> Last updated 2026-06-26.

---

## 1. One-liner & positioning

> **Give Sentinel a target agent. It plans attacks, executes them through the agent's real interfaces,
> observes what the agent (and its guardrails) actually did, judges each attempt pass/fail against a
> governed rubric, and emits a CI gate + audited report. Forge *builds* agents; Sentinel *proves they
> hold*.**

- **Identity it establishes:** *AI-platform security engineer* (not "AppSec engineer who uses AI").
- **Two demos, one story:** "I build governed agents **and** I red-team them in CI."
- **Why now:** the agent-security field is consolidating at the *prompt-firewall* layer (Lakera→Check
  Point, Promptfoo→OpenAI), but the **agentic, eval-gated, your-own-agents-in-CI verifier** sliver is
  still open. See [`../research/MARKET-RESEARCH-2026.md`](../research/MARKET-RESEARCH-2026.md).

## 2. Decisions (locked) and open toggles

**Locked**
- **Build approach:** standalone repo that **depends on the `forge_kernel` reuse spine** (AI Gateway,
  eval harness, governance/`reasonCode`, audit, observability). *Built-via-Forge is narrative only* —
  execution is Sentinel's own small graph, for demo stability. (~65% reuse.)
- **Primary target:** `ands-forge-os` in-process (import `build_forge`), driven by attack-injected
  visions/artifacts. **Secondary target:** the `ai-secops-copilot`. Targets sit behind a `Target` port.
- **Mode:** offline-deterministic by default ($0, reproducible for demo/CI); live LLM attacker optional.
- **Output:** governed pass/fail report (Markdown + JSON) + **CI exit code** + append-only audit with a
  `reasonCode` per attack.

**Open toggles (your call — defaults in bold)**
- Product name: **ANDS Sentinel** / AgentProbe / ANDS Verifier.
- Repo path: **`D:\ands-ai\ands-agent-verifier`** vs. a module inside the portfolio.
- v1 interface: **CLI + Markdown/JSON report** first; web dashboard deferred (stretch).

## 3. The attack surface in the REAL target (grounded in Forge OS code)

These are concrete, verified surfaces in `ands-forge-os` — not hypotheticals:

| # | Attack class | Real surface in Forge OS | Expected v1 result |
|---|---|---|---|
| **A** | **Indirect / RAG prompt injection** | The `vision` string is interpolated straight into agent prompts (`stubs.py` `_gateway_call`: `Produce … for vision: {ctx.run.vision}`); skill-pack `corpus` flows in as citations | **Catch** (seeded-vulnerable agent) + **pass** (isolated agent) |
| **B** | **Agent-governance / eval-gate bypass** ⭐ | `gates.py` `auto-if-eval` auto-approves with **no human** when `eval_score ≥ bar`; `reviewer.py` `_criterion_satisfied` scores by **token subset overlap** → a **keyword-stuffed, low-substance artifact inflates its score and auto-approves past the HITL gate** | **Catch** (live, unfakeable — real bug) |
| **C** | **Tool-use abuse / path traversal** | `tools/filesystem.py` `write_file`/`scaffold_repo` route through `tools/base.py` `safe_join` | **Pass** (defense holds) — shows true-negatives, no false alarms |
| **D** | **Multi-agent pipeline poisoning** | Upstream artifact content flows downstream via `ctx.inputs` (e.g. PRD → architect/scaffolder) | **Catch** (seeded) — cross-agent contamination |
| **E** | *(stretch)* Budget/loop exhaustion & run isolation | CLI `guard<50`, budget governor; per-run workspace/`thread_id` | Coverage probe; report-only in v1 |

> The combination of **B (a real catch)** + **C (a real pass)** is the credibility core: Sentinel finds
> a genuine governance bypass **and** correctly clears a hardened control — proving it isn't a
> false-positive generator.

## 4. Architecture (ports & adapters)

```
            ┌─────────────────────────── Sentinel run ───────────────────────────┐
 attack     │  Planner ──► Attacker (fan-out over classes) ──► Observer ──► Judge │ ──► Gate ──► Report
 corpus ───►│  (plan)      (drives Target via adapter)        (captures)  (scores)│     (CI)     (md+json+audit)
            └────────────────────────────────────────────────────────────────────┘
                                   │ Target port (protocol)
                  ┌────────────────┼─────────────────┐
            ForgeTarget        CopilotTarget      (future) HTTP/MCP target
          (in-process)        (in-process)
```

- **Planner** — selects attack classes + cases from the corpus for the declared target capabilities.
- **Attacker** — executes each case against the `Target` (fan-out across classes; bounded).
- **Observer** — captures the target's response, tool calls, gate decisions, audit events.
- **Judge** — scores each attempt against a per-class rubric (**reuses the eval harness**:
  attack = eval case, verdict = LLM-as-judge or deterministic check).
- **Gate** — aggregates verdicts → CI pass/fail (regression gate; known-bad must be caught).
- **Report** — Markdown + JSON; every verdict an audited record with `reasonCode` (e.g.
  `attack:gate-bypass:caught`, `attack:path-traversal:defended`).

**`Target` protocol (the one new seam):**
```python
class Target(Protocol):
    name: str
    capabilities: set[str]                  # {"vision_input","tools","multi_agent","eval_gate"}
    def run(self, attack: AttackCase) -> Observation: ...   # drive the agent, return what it did
```
`ForgeTarget` implements this over `build_forge()` (inject malicious vision/artifact, read back run
status, gate decisions, written files, audit). New target = new adapter; the harness is unchanged.

## 5. Reuse map (from `forge_kernel` / copilot — ~65%)
Eval harness + LLM-as-judge + regression gate (**the core**); governance + `reasonCode` + append-only
audit; AI Gateway (attacker/judge models, cost control); observability (trace every attack step);
prompt-injection isolation knowledge (inverted into attacks). **Net-new:** attack corpus (injection +
tool-abuse + gate-bypass patterns), the `Target` port + `ForgeTarget`/`CopilotTarget` adapters, the
planner/attacker/observer loop, the report.

## 6. v1 cut list (demoable in ~3–5 days, max ~1 week)

**In:**
- `Target` port + **`ForgeTarget`** (in-process) + `CopilotTarget`.
- Attack classes **B (gate-bypass) and C (path-traversal) fully**, each with **≥1 catch and ≥1 pass**;
  **A and D as seeded demo cases**.
- Deterministic offline attacker + judge; eval-as-gate; CLI; Markdown+JSON report; audit trail.
- A `--hardened` toggle (or a patched target variant) to flip the gate-bypass finding **red → green**
  for the demo.

**Cut / defer:** adaptive multi-turn attacks, live-LLM attacker on stage, web dashboard, HTTP/MCP
targets, class E (report-only), large public corpora (Garak/PyRIT import is post-v1).

## 7. Killer demo flow (self-referential)
1. `sentinel run --target forge-os` → suite executes; per-attack verdicts stream with cost/traces.
2. **The catch (B):** Sentinel submits a keyword-stuffed, low-substance artifact; Forge's
   `auto-if-eval` gate **auto-approves it with no human**. Sentinel flags
   `attack:gate-bypass:caught`, **CI gate goes RED**.
3. **The pass (C):** Sentinel attempts `../../etc/passwd` writes; `safe_join` blocks them; Sentinel
   reports `attack:path-traversal:defended` — *no false alarm*.
4. **Fix it live:** enable `--hardened` (require human on `auto-if-eval` when substance < threshold, or
   raise the bar / add a substance check) → re-run → **CI gate GREEN**.
5. **Close:** "Sentinel just red-teamed the agent OS I built five minutes ago, caught a real governance
   bypass, and gated it in CI. Models get commoditized; trust doesn't."

## 8. Success metrics
- **Coverage:** ≥4 attack classes exercised; B & C with both polarities (catch + pass).
- **Catch rate:** 100% on seeded-vulnerable cases (no missed known-bad).
- **No false-safe / no false-alarm:** hardened controls (C) report as passes.
- **CI:** runs as a gate in < ~2 min, deterministic, exit-code correct.
- **Auditability:** every verdict has a `reasonCode` and a trace.

## 9. Build sequence (for the dev chat)
1. Scaffold `ands-agent-verifier` (reuse `forge_kernel` as a dep); walking skeleton runs offline.
2. Define `AttackCase` / `Observation` / verdict schemas + the `Target` port.
3. `ForgeTarget` over `build_forge()`; prove a benign run round-trips.
4. Attack corpus for classes B & C (+ seeded A/D); deterministic attacker.
5. Judge via the eval harness (rubric per class) → verdicts.
6. Gate + CLI + Markdown/JSON report + audit (`reasonCode` per attack).
7. `--hardened` path that closes B; eval regression gate in CI.
8. Add `CopilotTarget`; polish + record the self-referential demo.

## 10. Risks & mitigations
- **Niche/education needed** → bundle as *the safety story for Forge* (one narrative, two demos).
- **"Just a fuzzer" perception** → emphasize **agentic + eval-gated + governed verdicts**, and the
  **real** Forge bug it catches (unfakeable).
- **Demo fragility** → fully deterministic offline; bounded fan-out; fixed corpus.
- **Target coupling** → everything behind the `Target` port; Forge bug fix shouldn't break Sentinel
  (keep a pinned `seeded-vulnerable` target variant for the regression demo).
```
