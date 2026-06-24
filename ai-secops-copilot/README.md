# AI Security Operations Copilot

> Governed, observable AI platform that triages security findings and drives the ticket lifecycle —
> LangGraph + RAG + MCP + evaluations + human-in-the-loop governance.

An enterprise AI platform that automates the security-finding lifecycle — analysis, prioritization,
governed ticket creation, and remediation tracking — using agentic workflows, retrieval-augmented
reasoning, evaluation pipelines, and confidence-gated human-in-the-loop governance.

It does **not** scan code. It ingests findings JSON (Semgrep / SARIF), reasons over them with security
knowledge (OWASP/CWE/CVE) via RAG, decides actions with a confidence score, and executes governed
ticket actions through an MCP tool layer — with full observability, cost tracking, and evaluation.

## Architecture (at a glance)

```text
Semgrep Findings → Finding Analysis Node → [AI Gateway → OpenAI/Claude]
                 → RAG (OWASP/CWE) → Ticket Decision Node → Governance Gate
                 → (Auto | Approval | Escalate) → Jira MCP → Metrics → Langfuse/OTel → Dashboard
```

Full diagram: [docs/diagrams/architecture.md](docs/diagrams/architecture.md).

## Quickstart

Everything below runs from the repo root.

```bash
# 0) End-to-end demo — one command, fully offline (no server, no keys, no network)
python scripts/demo_walkthrough.py      # narrates the whole lifecycle (see docs/demo/walkthrough.md)

# 1) Evaluation harness — runs TODAY with a bare Python install (no deps, no keys)
python evals/run_eval.py                # heuristic baseline over the 50-finding golden set
python evals/run_eval.py --gate         # add the CI regression gate

# 2) Agent runtime (Python + LangGraph) — governance gate + idempotency work today
cd services/agent-runtime && pip install -e ".[dev]" && pytest && cd ../..

# 3) Gateway (NestJS) — AI Gateway with provider fallback + cost/latency metrics
cd services/gateway && npm install && npm test && npm run start:dev && cd ../..

# 4) Local infra (used Day 5+): Postgres + pgvector and Redis
docker compose up -d
```

See per-area READMEs: [`evals/`](evals/README.md) ·
[`services/agent-runtime/`](services/agent-runtime/README.md) ·
[`services/gateway/`](services/gateway/README.md).

## Tech Stack (hybrid)

- Control plane / API: NestJS + TypeScript (`services/gateway`)
- Agent runtime: Python + LangGraph (`services/agent-runtime`)
- Vector store: Postgres + pgvector · Cache: Redis (semantic cache)
- LLMs: OpenAI + Claude (fallback) · Observability: OpenTelemetry + Langfuse
- Evals: DeepEval / RAGAS · MCP: Jira (real), ServiceNow (mock)

## Repository Layout

```text
ai-secops-copilot/
├─ README.md
├─ Makefile                        # common dev tasks (eval, test, infra-up, ...)
├─ docker-compose.yml              # local Postgres (pgvector) + Redis
├─ .env.example                    # root/shared local-dev config
├─ docs/
│  ├─ PRODUCT_VISION.md            # Locked product vision (resume/LinkedIn/interview source of truth)
│  ├─ architecture-decisions.md    # ADRs (the "why" behind each choice)
│  ├─ diagrams/architecture.md     # Mermaid diagrams
│  └─ planning/                    # Build planning + conversation log
├─ datasets/
│  ├─ findings/security-findings-v1.json   # Golden dataset: 50 labeled findings
│  ├─ knowledge/security-kb-v1.json        # RAG corpus: OWASP Top 10 + CWE guidance
│  ├─ samples/                             # sample Semgrep + SARIF reports for /ingest
│  └─ schema/security-findings-v1.schema.json  # JSON Schema for the dataset
├─ evals/                          # Evaluation harness
│  ├─ run_eval.py                  # CLI: load → predict → score → report → gate
│  ├─ metrics.py                   # accuracy, confusion matrix, P/R/F1 (stdlib)
│  └─ predictors.py                # heuristic baseline (+ runtime predictor stub)
├─ services/
│  ├─ gateway/                     # NestJS control plane + AI Gateway (single LLM egress)
│  └─ agent-runtime/               # Python LangGraph agent runtime
├─ infra/postgres/                 # init.sql (enables pgvector) + knowledge.sql (RAG schema)
└─ scripts/                        # run-checks.ps1 / run-checks.sh
```

## Status

Vision, architecture, scope, and decisions are **locked**.

**Day 1 complete:** golden dataset (50 labeled findings) + runnable eval harness
(heuristic baseline: 86% severity accuracy, 100%/37.5% FP precision/recall) +
hybrid scaffold (Python LangGraph runtime with a working governance gate &
idempotency; NestJS AI Gateway with provider fallback + cost/latency metrics).

**Day 2 complete — walking skeleton end-to-end:** `Finding → analysis (validated
structured output) → governance gate → action (auto-ticket | human-approval queue
| escalate)`, with idempotent mock ticketing and a human-in-the-loop approval flow
(`POST /analyze`, `/approvals`, `/tickets`, `/escalations`). The analysis runs on a
deterministic, offline **LLM stand-in** (no keys; the AI Gateway swaps a real model
in on Day 11 behind the same seam) with bounded re-prompt on invalid output and
prompt-injection isolation of finding text.

The eval's `runtime` predictor now exercises the node's real reasoning. Before/after
vs the Day-1 heuristic baseline (same 50-finding golden set):

| Metric | Heuristic (Day 1) | Runtime (Day 2) | Δ |
| --- | --- | --- | --- |
| Severity accuracy | 86.0% | 96.0% | +10.0 |
| Action accuracy | 84.0% | 100.0% | +16.0 |
| False-positive recall | 37.5% | 100.0% | +62.5 |
| False-positive F1 | 54.5% | 100.0% | +45.5 |

```bash
python evals/run_eval.py --predictor heuristic --quiet            # writes baseline
python evals/run_eval.py --predictor runtime --gate \
  --baseline evals/runs/latest.json                               # shows the delta
```

> Honest caveat: the deterministic analyzer was calibrated on this same golden set,
> so these numbers reflect a strong rules baseline, not held-out generalization.
> The real test is the LLM on unseen findings once the AI Gateway is wired (Day 11);
> the eval harness and gate are what make that comparison measurable.

**Day 3 complete — real Jira + provider-agnostic ticketing:** the action stage now
runs behind a `TicketProvider` abstraction (ADR-008) with three idempotent adapters
(ADR-009) — in-memory **mock** (default), **real Jira Cloud** (REST v3; idempotency
via a `finding-<hash>` label search that survives restarts), and a **ServiceNow
mock** — plus a **dead-letter queue** so a provider/API failure parks the decision
instead of losing it. Select with `TICKET_PROVIDER`; it stays offline-by-default and
falls back to `mock` if Jira creds are absent. The Jira adapter is unit-tested with a
mocked HTTP transport (no live tenant needed).

**Day 4 complete — Semgrep/SARIF ingestion:** raw scanner reports now normalize into
the common finding contract (ADR-007) via format-detecting adapters — **Semgrep JSON**
(`semgrep --json`) and **SARIF v2.1.0** (the OASIS interchange format many scanners
emit). `POST /ingest` auto-detects the format, normalizes every finding (CWE/OWASP/
severity extraction, stable ids, code snippets), validates each against the contract,
and drives them through the full pipeline, returning a per-finding result + outcome
summary. Clean-room sample reports live in [`datasets/samples/`](datasets/samples/).
The Copilot ingests findings — it does not scan — so no scanner CLI or keys are needed.

**Day 5 complete — RAG knowledge layer:** analysis is now **grounded** in a clean-room
**OWASP Top 10 (2021) + CWE** knowledge base ([`datasets/knowledge/`](datasets/knowledge/))
and every decision carries **citations** (ADR-001). Retrieval sits behind a
`KnowledgeRetriever` seam: the default is a pure-stdlib **lexical retriever** (TF-IDF +
exact CWE/OWASP id boost) that runs offline and deterministically; **pgvector**
(ADR-002, schema in [`infra/postgres/knowledge.sql`](infra/postgres/knowledge.sql))
slots in behind the same interface when `DATABASE_URL` is set. Retrieved text is fed to
the LLM prompt as a **trusted** block, kept separate from the untrusted finding
(ADR-011). New `GET /knowledge/search`; `/analyze` responses now include
`decision.citations`.

**Day 6 complete — evaluation upgrade + CI gate:** the harness now also measures
**RAG retrieval quality** (RAGAS-style context relevance over the real retriever:
KB coverage, hit@1/hit@k, MRR, plus the list of CWEs missing from the corpus) and runs
an **LLM-as-judge** reasoning-quality pass behind a swappable `Judge` seam
(deterministic offline rubric today; real LLM judge on Day 11). The regression gate now
covers classification **and** retrieval **and** judge scores, and a **GitHub Actions CI
workflow** ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs ruff +
pytest + the eval gate on every push/PR. Run it all with
`python evals/run_eval.py --predictor runtime --all --gate`.

**Day 7 complete — governance hardening + audit trail:** the confidence gate is now a
small, auditable **policy engine** (ADR-005). Auto-execution is **asymmetric by risk**:
creating a ticket auto-runs at `auto_threshold` (0.90), but **auto-suppressing** a finding
must clear a stricter `suppress_auto_threshold` (0.95) — dismissing a real vuln is the
costlier error. Every decision now carries a machine-readable **`reasonCode`**, and an
append-only **audit trail** (`GET /audit`) records what was decided, why, and by whom
(`system` vs `human`). Thresholds are **tuned from eval data, not guessed**: a new
governance eval pass (`evals/governance_eval.py`) reports automation/review/escalation
rates, **auto-action accuracy** ("when we act without a human, are we right?"), and an
auto-threshold **sweep** showing the autonomy/safety trade-off. The regression gate now
also enforces `auto_action_accuracy ≥ 0.99` (no wrong autonomous actions). Run with
`python evals/run_eval.py --predictor runtime --governance --gate`.

**Day 8 complete — demo milestone (single-page dashboard):** the agent runtime now serves
a dependency-free **operations dashboard** at `/` (→ `/dashboard`) that wires the whole flow
into one memorable screen: KPI cards (findings processed, tickets created, automation /
approval / escalation rates, latency), an autonomy-split bar, the live **audit trail**, and a
**pending-approvals** panel with working approve/reject buttons. A one-click **`POST /demo/seed`**
ingests the bundled Semgrep + SARIF samples so the canonical story plays instantly — a critical
SQLi **auto-creates** a ticket, a medium finding **waits for approval**, clear false positives
are **auto-suppressed**, and an ambiguous case **escalates**. KPIs come from a new `GET /metrics`
(pure aggregation over the audit trail; per-finding latency now recorded). Run it with
`python -m uvicorn app.main:app --port 8088` and open `http://localhost:8088/`.

The main table is a **current-state findings view** (`GET /findings`): the append-only audit
trail is a compliance event log, so the dashboard projects it down to **one row per finding**
(deduped by `finding_hash`) with its single linked ticket and an "evaluated ×N" counter.
Re-running the demo therefore updates findings in place — it never duplicates rows or ticket
links — which is also the idempotency guarantee made visible (events grow, findings/tickets
don't). A **Reset** button clears the in-memory state for a fresh run.

**Day 9 complete — compiled LangGraph (routing + checkpointed HITL):** the walking-skeleton
nodes are now wired into a real **compiled LangGraph** (`app/graph/build.py`, driven by
`GraphRunner`) with explicit `GraphState`, **conditional routing** on the governance
disposition (auto-execute / escalate → `execute`; human-approval → `await_approval`), a
**MemorySaver checkpointer**, and a genuine **human-in-the-loop interrupt**: a medium-confidence
finding *pauses* the graph (`POST /graph/analyze` → `awaiting_approval` + `threadId`) and is
*resumed in a later request* (`POST /graph/resume/{thread_id}` with approve/reject) — durable
HITL, not a synchronous block. `GET /graph` returns the nodes + mermaid. The LLM client and
retriever are injected via LangGraph **config** (not checkpointed state) so the graph serializes
cleanly. The dependency-free `run_pipeline` remains a fallback running the *same* node functions
(one source of truth for the reasoning); `/health` reports the active orchestration
(`langgraph` vs `inline`).

Current numbers (runtime predictor, n=50): severity **96.0%**, action **100.0%**,
FP-F1 **100.0%**, retrieval **hit@k 100.0%** (KB coverage **56.0%**), judge **100.0%**,
governance **auto-action accuracy 100.0%** (34% automated, 60% to humans, 6% escalated).

**Day 10 complete — durable persistence (memory → SQLite → Postgres):** runtime state
(audit trail, approvals, escalations, dead-letter) and the LangGraph checkpointer now sit
behind a **persistence seam** (`app/persistence/`) selected from `DATABASE_URL`: in-memory
(offline default), durable **SQLite** (local/CI), and **Postgres** in production (identical
schema, `infra/postgres/state.sql`). All stores share one method contract so the runtime is
backend-agnostic, and an unavailable durable backend degrades to memory so the service always
starts. Approvals and the audit trail now **survive a restart** (verified: seed 6 findings,
restart the process, all 6 are still there) — so a paused HITL run and the compliance log are
no longer lost on a crash. `GET /health` reports the active `persistence` backend; the
checkpointer upgrades from `MemorySaver` to `PostgresSaver` through the same seam when the
optional package is installed.

Current numbers (runtime predictor, n=50): severity **96.0%**, action **100.0%**,
FP-F1 **100.0%**, retrieval **hit@k 100.0%** (KB coverage **56.0%**), judge **100.0%**,
governance **auto-action accuracy 100.0%** (34% automated, 60% to humans, 6% escalated).

**Day 11 complete — AI Gateway (single LLM egress):** every model call now flows through one
in-process gateway (`services/agent-runtime/app/gateway/`) behind the existing `LLMClient`/`Judge`
seams. It owns **task-aware routing** (cheap model first for triage, stronger model first for the
judge), **ordered fallback** (OpenAI → Claude → deterministic), a **semantic cache** (lexical
offline; embeddings in prod), and **cost/latency/token tracking** — surfaced at `GET /gateway/metrics`
and on the dashboard. With no API keys it resolves to the always-on deterministic provider, so the
runtime stays fully offline, reproducible, and free; set `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` to
light up real models, with deterministic as the final fallback so a provider outage degrades instead
of fails. Verified live: re-seeding identical findings produced a **50% cache hit rate** at $0 cost.
The Python egress mirrors the NestJS `services/gateway` scaffold (same `llm.types.ts`/`cost.ts`
contract) so the hybrid Python+Node story is real while the runtime stays testable in one harness.

**Day 12 complete — observability & ops:** added an `app/observability/` layer with three
offline-first pillars. **Tracing** — every pipeline stage and gateway call is a `contextvars`-linked
span emitted as a structured JSON log (`/observability/traces`), with optional OpenTelemetry OTLP
export when `OTEL_ENABLED=true`. **Metrics** — a rolling time-series powers cost/latency-over-time
charts (`/observability/timeseries`) and a hand-written **Prometheus** scrape target
(`/observability/metrics`, no client library). **Alerting** — a transparent rule engine
(`/observability/alerts`) fires on escalation rate, approval backlog, gateway fallback rate, cost per
request, p95 latency, and dead-letter presence, surfaced on the dashboard and in `/health`. The
dashboard gained an alerts banner and an LLM-latency sparkline. Verified live: seeding produces full
trace trees (`pipeline.run → ingest/finding_analysis/ticket_decision/execute` + `llm.complete`), a
valid Prometheus exposition, and **zero false alerts offline** (also fixed a fallback-rate bug so a
provider skipped as *not-configured* no longer counts as a fallback).

**Day 13 complete — containerization & CI/CD:** both services now ship as multi-stage, non-root
Docker images (Python agent-runtime, NestJS gateway), wired into a one-command `docker compose up`
stack (Postgres/pgvector + Redis + both apps, runnable offline). The GitHub Actions pipeline was
hardened into three jobs — a Python **3.11/3.12 matrix** (lint + tests + eval gate), a **Node** job
(gateway lint + build + jest), and an **images** job that builds both containers on every PR and
publishes them to GHCR on `master` — plus concurrency cancellation, least-privilege permissions,
dependency caching, and a `Makefile` mirroring CI (`make check`). The runtime image preserves the
repo layout so containerization needed **zero app code changes**; verified locally that the gateway
builds and its 5 jest tests pass, the compose/CI YAML is valid, and the Python gate stays green.

**Day 14 complete — end-to-end demo polish & docs:** a single, reproducible
[`scripts/demo_walkthrough.py`](scripts/demo_walkthrough.py) now narrates the entire lifecycle
**offline, with no server, no API keys, and no network** — it drives the runtime in-process
(FastAPI `TestClient`) over the bundled Semgrep + SARIF reports and prints each stage: health →
reset+seed → current-state findings (SQLi auto-tickets, a medium waits, FPs suppressed, an
ambiguous critical escalates) → a human **approves** the pending finding → **idempotency** (re-seed:
events grow, findings/tickets don't) → KPIs → gateway cache/cost (50% hit @ $0) → zero firing
alerts → the audit trail. It exits non-zero on any failure, so it doubles as an end-to-end smoke
test (`make demo`). The recorded run lives in [`docs/demo/walkthrough.md`](docs/demo/walkthrough.md),
and the architecture diagrams gained an **as-built (Day 14)** topology that reconciles the target
vision with what actually runs today ([docs/diagrams/architecture.md](docs/diagrams/architecture.md) §9).

**Day 15 complete — multi-tenant isolation & API auth:** the runtime is now multi-tenant. A
`TenantRegistry` gives every tenant its **own** isolated state (audit trail, approvals,
escalations, dead-letter, ticket provider, AI Gateway cache/cost, and graph checkpointer), so one
customer can never see or affect another's data (durable SQLite is isolated per-tenant file).
The data plane is authenticated two ways behind one seam (ADR-017): an **API key** (`X-API-Key` or
`Authorization: Bearer`, mapped to a tenant via `API_KEYS`) and a **signed HS256 JWT** (`JWT_SECRET`,
tenant from the `tenant` claim, verified with the standard library — no PyJWT). A per-tenant
fixed-window **rate limiter** (`RATE_LIMIT_RPM`) returns `429 + Retry-After`. It's **off by default**
(`AUTH_ENABLED=false`; pick a tenant with `X-Tenant-Id`, default `public`) so the offline demo and
all 134 tests run unchanged; flip one env var to enforce. `/health`, `/dashboard`, and
`/governance/preview` stay open for liveness. 20 new tests cover JWT verification, auth modes,
tenant isolation, and rate limiting.

**Next — Day 16:** ticket lifecycle sync & remediation tracking — bi-directional status sync
(ticket closed → finding resolved), SLA timers, and a remediation view on the dashboard.

## Documentation

- [Product Vision](docs/PRODUCT_VISION.md)
- [Demo Walkthrough](docs/demo/walkthrough.md) — one-command offline run, narrated
- [Architecture Decisions](docs/architecture-decisions.md)
- [Architecture Diagrams](docs/diagrams/architecture.md)
- [Build Plan & Notes](docs/planning/AI_PLATFORM_ENGINEER_PREP.md)
- [Interview & Profile Prep](docs/planning/interview-prep.md)

---

Security-domain modeling is implemented clean-room from public standards (SARIF, OWASP, CWE, Semgrep
public output). No proprietary code, schema, data, or credentials are used.
