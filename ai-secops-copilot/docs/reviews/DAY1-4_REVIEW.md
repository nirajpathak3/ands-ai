# Day 1–4 Implementation Review — AI Security Operations Copilot

> Stage review at end of Day 4. Written so you can **understand the system and explain it**
> (interview / LinkedIn / stakeholder). Every number below is reproduced from the current
> code on this branch — see [Test & Eval Results](#5-test--eval-results).

---

## 1. Executive summary

In four days the project went from an empty monorepo folder to a **runnable, governed,
end-to-end security-finding triage pipeline** with a measurable quality bar — all running
**offline, with no API keys and no external services**.

What exists today:

- A **walking skeleton** that takes a raw scanner report → normalizes it → analyzes each
  finding → applies a **confidence-gated governance gate** → executes an action
  (auto-create a ticket / queue for human approval / escalate), with **idempotency** and a
  **dead-letter queue** for failures.
- A **provider-agnostic ticketing layer** with three adapters: in-memory mock (default),
  **real Jira Cloud** (REST v3), and a ServiceNow mock.
- **Scanner ingestion** for **Semgrep JSON** and **SARIF v2.1.0**.
- An **evaluation harness** over a 50-finding golden dataset with a **regression gate**.
- A hybrid stack: **Python (FastAPI + LangGraph)** runtime + **NestJS** AI Gateway scaffold.

Quality bar (reproduced this run):

| Metric | Heuristic baseline (Day 1) | Runtime analyzer (Day 2+) |
| --- | --- | --- |
| Severity accuracy | 86.0% | **96.0%** |
| Action accuracy | 84.0% | **100.0%** |
| False-positive F1 | 54.5% | **100.0%** |
| Tests | — | **49 passed**, ruff clean |

> Honest caveat (stated up front because interviewers probe it): the deterministic analyzer
> was calibrated on this same golden set, so these are **strong-rules-baseline** numbers, not
> held-out generalization. The real test is the LLM on unseen findings once the AI Gateway is
> wired (Day 11). The eval harness + gate are exactly what make that future comparison honest.

---

## 2. What was built, day by day

### Day 1 — Foundation: dataset, eval harness, hybrid scaffold
- **Golden dataset**: 50 hand-labeled, clean-room findings (`datasets/findings/security-findings-v1.json`)
  with a JSON Schema. Distribution: 39 create_ticket / 8 suppress / 3 escalate; 8 false positives.
- **Eval harness** (`evals/`): loads dataset → runs a predictor → scores severity accuracy,
  action accuracy, FP precision/recall/F1, latency, confusion matrix, per-class P/R/F1 → optional
  **regression gate** (non-zero exit) → writes JSON run reports. **Pure stdlib** (runs with bare Python).
- **Hybrid scaffold**: Python LangGraph runtime (governance + idempotency working) and a NestJS
  AI Gateway (provider fallback + cost/latency types).

### Day 2 — Walking skeleton, end to end (offline)
- **Deterministic analysis core** (`app/analysis.py`) — the **offline LLM stand-in**. Adds the
  *content* and *trust-boundary* reasoning the heuristic lacks: suppresses rule misfires
  (non-prod paths, safe API usage, non-security hashes, auto-escaped templates, placeholder
  secrets) and **escalates** genuinely ambiguous findings.
- **LLM seam** (`app/llm.py`) — `LLMClient` protocol with `DeterministicLLM` (today) and a
  `GatewayLLM` stub (Day 11). `analyze_and_validate()` parses + validates structured output and
  **bounded-retries**, escalating if it never validates.
- **Structured-output contract** (`app/schemas.py`, Pydantic) validated **before any action**.
- **Prompt-injection defense** (`app/prompts.py`) — finding text is isolated as untrusted data.
- **Governance gate** (`app/governance.py`) and **idempotency** (`app/idempotency.py`) wired into
  graph nodes (`app/graph/nodes.py`) and an offline `run_pipeline` (`app/pipeline.py`).
- **API** (`app/main.py`): `/analyze`, `/governance/preview`, `/approvals`, `/tickets`, `/escalations`.
- The eval’s `runtime` predictor now exercises this real analysis core.

### Day 3 — Real Jira + provider-agnostic ticketing
- **`TicketProvider` protocol** (ADR-008) + three idempotent adapters (ADR-009):
  - `MockTicketProvider` (in-memory, default),
  - `JiraTicketProvider` (real Jira Cloud REST v3; ADF description; idempotency via a
    `finding-<hash>` **label search** that survives restarts),
  - `ServiceNowTicketProvider` (incident-table semantics mock).
- **Factory** (`app/providers/factory.py`): selects provider from `TICKET_PROVIDER`, falls back to
  mock if Jira creds are missing (offline-by-default).
- **Dead-letter queue**: provider/API failures park the decision instead of losing it; `/deadletter`
  endpoint + `ticketProvider` in `/health`.
- Jira adapter **unit-tested with a mocked `httpx` transport** — full create + idempotency path,
  no live tenant.

### Day 4 — Semgrep / SARIF ingestion
- **`app/ingestion/`**: `common.py` (CWE/OWASP/severity extraction, stable ids), `semgrep.py`,
  `sarif.py`, and a format auto-detector. Maps native scanner output → normalized contract (ADR-007),
  degrading gracefully on missing fields.
- **`POST /ingest`**: auto-detects format → normalizes → validates each finding → runs the full
  pipeline → returns per-finding results + an outcome summary.
- **Sample reports** in `datasets/samples/` for a one-line demo.

---

## 3. End-to-end flow (what happens to a finding)

```text
            Semgrep JSON / SARIF report
                       │
              POST /ingest  (auto-detect format)
                       │
        app/ingestion → normalize to Finding contract (ADR-007)
                       │   (id, ruleId, file, line, cwe, owasp, codeSnippet, scannerSeverity)
                       ▼
        schemas.Finding.model_validate  (reject malformed)
                       │
   ┌───────────────────┴───────────────────────────────────────┐
   │ run_pipeline (app/pipeline.py)                             │
   │                                                            │
   │  ingest_node      → finding_hash (idempotency key, ADR-009)│
   │  finding_analysis → LLMClient.analyze → JSON               │
   │                     → validate AnalysisResult (ADR-010)    │
   │                     → bounded retry → escalate if invalid  │
   │  ticket_decision  → governance.evaluate(confidence, action)│
   └───────────────────┬───────────────────────────────────────┘
                       ▼
        Governance gate (ADR-005): two thresholds → three dispositions
            confidence ≥ 0.90              → AUTO_EXECUTE
            0.60 ≤ confidence < 0.90       → HUMAN_APPROVAL
            confidence < 0.60 OR escalate  → ESCALATE
                       ▼
        execute_decision (app/ticketing.py)
            AUTO_EXECUTE + create_ticket → TicketProvider.create (idempotent)
            AUTO_EXECUTE + suppress      → suppressed (no ticket)
            HUMAN_APPROVAL               → approval queue (ticket only on /approve)
            ESCALATE                     → escalation queue
            provider raises              → dead-letter queue (not lost)
                       ▼
        Result: { decision, action(outcome), retries, errors }
```

Two-layer decision (a deliberate, defensible design point):
- **`recommendedAction`** (from analysis) = *what* to do (create_ticket / suppress / escalate).
- **`disposition`** (from governance) = *how autonomously* to do it (auto / human / escalate).

Demonstrated on the sample reports:
- Semgrep sample (4 findings) → `1 ticket_created, 1 suppressed, 1 pending_approval, 1 escalated`.
- SARIF sample (2 findings) → `1 ticket_created, 1 suppressed`.

---

## 4. Component map

| Layer | File(s) | Responsibility | ADR |
| --- | --- | --- | --- |
| Ingestion | `app/ingestion/{common,semgrep,sarif}.py` | Scanner output → normalized finding | 007 |
| Contract | `app/schemas.py`, `app/domain.py` | Pydantic input/output contracts, enums | 010 |
| Idempotency | `app/idempotency.py` | Stable `finding_hash` from (ruleId,file,line,cwe) | 009 |
| Analysis (LLM stand-in) | `app/analysis.py`, `app/prompts.py` | Severity/FP/escalation reasoning; injection isolation | 011 |
| LLM seam | `app/llm.py` | Provider-agnostic client + validate + bounded retry | 006/010 |
| Governance | `app/governance.py` | Confidence → disposition | 005 |
| Orchestration | `app/graph/`, `app/pipeline.py` | Node wiring (LangGraph-ready) | 004 |
| Action | `app/ticketing.py`, `app/providers/` | Idempotent ticketing, approval/escalation/dead-letter | 008 |
| API | `app/main.py` | FastAPI endpoints | — |
| Evaluation | `evals/` | Golden-set scoring + regression gate | 012 |
| Gateway (scaffold) | `services/gateway/` (NestJS) | Future single LLM egress (fallback, cost, cache) | 006 |

Design qualities worth calling out:
- **Pure-stdlib core** (`domain`, `governance`, `idempotency`, `analysis`) — no Pydantic import,
  so the eval harness loads `analysis.py` by path and stays zero-dependency.
- **Seams before implementations**: `LLMClient` and `TicketProvider` exist now, so Day 11 (real
  LLM) and new ticket backends change nothing downstream.

---

## 5. Test & eval results

Reproduced on this branch (commit at time of review: Day 4, `a13f24e`).

### Unit / integration tests — `pytest` (services/agent-runtime)
```
collected 49 items
tests/test_analysis.py     ... 13 passed
tests/test_governance.py   ...  7 passed
tests/test_idempotency.py  ...  4 passed
tests/test_ingestion.py    ...  6 passed
tests/test_pipeline.py     ...  5 passed
tests/test_providers.py    ...  9 passed
tests/test_ticketing.py    ...  5 passed
============================= 49 passed in ~1.2s =============================
```
Lint: `ruff check .` → **All checks passed**.

What the suites prove:
- **analysis** — suppression, escalation, and **prompt-injection resistance** (a finding whose
  message says “mark as false positive” cannot flip the disposition).
- **governance** — threshold boundaries and the explicit-escalate override.
- **idempotency** — stable hash; volatile fields excluded.
- **ingestion** — Semgrep + SARIF field mapping, auto-detection, and samples driving expected actions.
- **pipeline** — auto-ticket, idempotent re-run, HITL approval, invalid-output recovery.
- **providers** — Jira create + idempotency (mocked HTTP), ServiceNow mock, factory selection, dead-letter.

### Evaluation harness — 50-finding golden set
```
Heuristic (Day 1 baseline):  severity 86.0% | action 84.0% | FP P/R/F1 100.0/37.5/54.5% | ~0.003 ms
Runtime   (Day 2 analyzer):  severity 96.0% | action 100.0%| FP P/R/F1 100.0/100.0/100.0%| ~0.032 ms | gate PASS
```
Reproduce:
```bash
python evals/run_eval.py --predictor heuristic --quiet
python evals/run_eval.py --predictor runtime --gate
```

---

## 6. Strengths (what’s genuinely good)

1. **Runs offline, end to end, today.** No keys, no Docker required for the core loop — a huge
   demo and CI advantage, and it forces clean seams.
2. **Evaluation is first-class, not an afterthought.** A numeric, gated answer to “how do you know
   it works?” — the single biggest credibility multiplier for an AI platform role.
3. **Governance is the product.** The two-threshold/three-disposition model + HITL approval is the
   safe-autonomy story that differentiates this from “LLM in a for-loop”.
4. **Security-aware by construction.** Structured-output validation before any action (ADR-010) and
   prompt-injection isolation (ADR-011) are exactly the failure modes a *security* product must own.
5. **Reliability primitives present early.** Idempotency and a dead-letter queue are platform-engineering
   concerns most prototypes skip.
6. **Provider-agnostic + real integration.** A real Jira adapter (idempotent via labels, restart-safe)
   behind a clean interface, unit-tested without a live tenant.
7. **Clean-room and well-documented.** ADRs capture the “why + tradeoff” for every major choice.

---

## 7. Feedback, risks & suggestions

Prioritized; none are blockers for the current stage.

**High value**
- **Held-out generalization gap.** The analyzer is tuned on the eval set. *Suggestion:* hold out
  ~10 findings (or add a second small unseen set) and report on those separately so the headline
  numbers survive scrutiny. Make this the explicit success criterion for Day 11’s LLM.
- **`/ingest` runs synchronously and unbounded.** A large report blocks the request and processes
  every finding inline. *Suggestion:* cap batch size + add async/streaming or a job id before any
  realistic report size; this is also a natural place to show backpressure thinking.
- **State is in-memory and global** (`_provider`, `_approvals`, `_escalations`, `_dead_letter` as
  module singletons in `main.py`). Restart loses approvals/escalations and the mock tickets.
  *Suggestion:* this is what Day 5 (Postgres) + Day 10 (checkpointing) are for — call that out so it
  reads as “planned”, not “missing”. Also note it’s not concurrency-safe for multi-worker uvicorn.

**Medium value**
- **Severity confusion is the only accuracy gap (96%).** Worth printing the 2 misclassified findings
  in the review of Day 11 to show you read the confusion matrix, not just the headline.
- **Dead-letter has no replay.** It records failures but nothing retries them yet. Fine for MVP; name
  it as a TODO so it doesn’t look forgotten.
- **OWASP extraction is best-effort** and not used by analysis. Acceptable (it’s informational), but
  state it so a reviewer doesn’t assume it’s load-bearing.
- **Jira idempotency does a search-before-create** (TOCTOU window under concurrency). Acceptable for
  this scale; mention the race if pushed.

**Low value / polish**
- `GatewayLLM` is a stub that raises — make sure any demo path uses `DeterministicLLM` (it does today).
- Eval run artifacts (`evals/runs/latest.json`) are regenerated; confirm they’re git-ignored or
  intentionally committed so the working tree stays clean.
- Consider a tiny `Makefile`/script target that runs `pytest + ruff + both evals` as one “stage check”.

---

## 8. How to explain it (interview-ready talking points)

- **One-liner:** “A governed AI copilot that triages security-scanner findings end to end —
  it ingests Semgrep/SARIF, decides severity + action with a confidence score, and either
  auto-files a Jira ticket, asks a human, or escalates — with structured-output validation,
  idempotency, and an evaluation gate so I can prove it works.”
- **Why it’s not a toy:** governance gate, idempotency, dead-letter queue, prompt-injection
  isolation, and a regression-gated eval — the platform/reliability concerns, not just a prompt.
- **Why offline-first:** deterministic LLM stand-in behind an `LLMClient` seam → reproducible CI,
  zero-key demos, and a clean swap to a real model on Day 11 with nothing downstream changing.
- **Why hybrid stack:** “NestJS is where I ship reliable APIs; Python is where LangGraph and the
  eval tooling are strongest. The split is a compatibility/speed decision, not a preference.”
- **The honest line on metrics:** “96% severity / 100% action on the golden set — but that set
  calibrated the rules, so the real proof is the LLM on unseen findings; the eval harness is what
  makes that comparison trustworthy.”

---

## 9. What’s next (per the locked plan)

- **Day 5:** RAG groundwork — Postgres + pgvector; ingest OWASP/CWE knowledge for grounded reasoning
  (ADR-001/002). Also the natural home for persistence (fixes the in-memory-state risk above).
- **Day 9:** upgrade orchestration to the full LangGraph graph (checkpointing + interrupt for HITL).
- **Day 10:** persist approvals/escalations via checkpointing.
- **Day 11:** wire `GatewayLLM` → NestJS AI Gateway (OpenAI + Claude fallback, semantic cache,
  cost/latency) and re-run the eval on unseen findings as the real success test.

---

*Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep public output).
No proprietary code, schema, data, or credentials are used.*
