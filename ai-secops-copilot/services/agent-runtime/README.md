# Agent Runtime (Python + LangGraph)

The orchestration core of the AI Security Operations Copilot. Models the locked
flow end to end:

```text
scanner report (Semgrep/SARIF) -> ingest/normalize -> idempotency hash
  -> RAG (retrieve OWASP/CWE) -> Finding Analysis Node -> Ticket Decision Node
  -> Governance Gate -> execute (auto-ticket | approval queue | escalate)
```

- **Ingestion** — normalizes raw **Semgrep JSON** and **SARIF v2.1.0** reports into the common finding contract (ADR-007); the Copilot ingests findings, it does not scan. **Implemented.**
- **RAG knowledge layer** — retrieves **OWASP/CWE** guidance (ADR-001) to ground analysis and **cite** every decision. Offline pure-stdlib lexical retriever (TF-IDF + exact CWE/OWASP id boost) by default; **pgvector** (ADR-002) slots in behind the same `KnowledgeRetriever` seam when `DATABASE_URL` is set. Retrieved text is passed to the LLM prompt as a **trusted** block, kept separate from the untrusted finding. **Implemented.**
- **Finding Analysis Node** — analyzes a finding into `{severity, confidence, reason, recommendedAction}` through the `LLMClient` seam and **validates the structured output** (Pydantic) before anything acts on it, bounded-retrying on invalid output (ADR-010). Finding text is treated as untrusted input, isolated from instructions (ADR-011). **Implemented.**
- **Ticket Decision Node + Governance Gate** — maps confidence → disposition (auto-execute / human-approval / escalate). **Implemented.**
- **Ticketing + HITL** — provider-agnostic ticketing (ADR-008) with idempotent adapters (ADR-009): in-memory **mock** (default), **real Jira** (Cloud REST v3, idempotent via a `finding-<hash>` label search), and a **ServiceNow mock**. Human-approval queue, escalation queue, and a **dead-letter queue** for provider failures. **Implemented.**

> **The LLM defaults to a deterministic offline stand-in** (`app/analysis.py` via
> `DeterministicLLM`), so the whole pipeline runs with no API keys and is fully
> reproducible in CI. Since Day 11 every model call flows through the AI Gateway
> (`app/gateway/`): set `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` to use a real model
> behind the same `LLMClient` seam, with deterministic as the final fallback —
> nothing downstream changes.

## Demo (offline, one command)

```bash
# from the repo root — narrates the whole lifecycle with no server, keys, or network:
python scripts/demo_walkthrough.py        # (or: make demo)
```

See the recorded run in [`docs/demo/walkthrough.md`](../../docs/demo/walkthrough.md).

## Status (Day 16 — ticket lifecycle sync & remediation tracking)

| Piece | State |
| --- | --- |
| **Remediation & SLA** (`app/remediation.py`: SLA timers, MTTR, remediation view + sync) | ✅ implemented + tested |
| **Multi-tenancy** (`app/tenancy.py`: per-tenant state/provider/gateway/graph; SQLite per-tenant file) | ✅ implemented + tested |
| **API auth** (`app/auth.py`: API key + stdlib HS256 JWT, tenant resolution) | ✅ implemented + tested |
| **Rate limiting** (`app/ratelimit.py`: per-tenant fixed window, 429 + Retry-After) | ✅ implemented + tested |
| **Demo walkthrough** (`scripts/demo_walkthrough.py`: offline end-to-end, doubles as smoke test) | ✅ implemented |
| **Container image** (multi-stage, non-root, healthcheck) + **compose** stack | ✅ builds in CI |
| **CI/CD** (py 3.11/3.12 matrix, Node gateway job, image build + GHCR publish) | ✅ implemented |
| Observability (in-process tracing + structured logs, Prometheus exposition, alert engine) | ✅ implemented + tested |
| AI Gateway (task routing, ordered fallback, **semantic cache**, cost/latency tracking) | ✅ implemented + tested |
| Providers (deterministic offline default; OpenAI + Anthropic when keys present) | ✅ implemented + tested |
| Persistence seam (audit/approvals/escalations/dead-letter; memory / SQLite / Postgres) | ✅ implemented + tested |
| Checkpointer seam (`MemorySaver` default; `PostgresSaver` when configured) | ✅ implemented + tested |
| Compiled LangGraph (conditional routing, checkpointer, human-approval **interrupt/resume**) | ✅ implemented + tested |
| Operations dashboard (`GET /` → `/dashboard`, KPIs + findings + approvals, one-click seed/reset) | ✅ implemented + tested |
| **Findings view** (`GET /findings`: current-state, deduped by hash, linked ticket) | ✅ implemented + tested |
| **Metrics** (`GET /metrics`: automation/approval/escalation rates, latency, decision events) | ✅ implemented + tested |
| Governance policy engine (asymmetric auto-suppress bar, reason codes) | ✅ implemented + unit-tested |
| Audit trail (`GET /audit`: who/what/why per decision) | ✅ implemented + tested |
| Ingestion: Semgrep JSON + SARIF v2.1.0 -> finding contract | ✅ implemented + tested |
| RAG: OWASP/CWE corpus + lexical retriever + citations | ✅ implemented + tested |
| Finding analysis (deterministic LLM stand-in) + structured-output validation | ✅ implemented + tested |
| Ticketing adapters: mock, **real Jira (REST v3)**, ServiceNow mock | ✅ implemented + tested |
| Idempotent create (in-memory map / Jira label search), dead-letter on failure | ✅ implemented + tested |
| HITL approval queue, escalation queue | ✅ implemented + tested |
| `GET /graph`, `POST /graph/analyze`, `POST /graph/resume/{thread_id}`, `GET /dashboard`, `GET /metrics`, `GET /findings`, `POST /demo/seed`, `POST /demo/reset`, `POST /analyze`, `POST /ingest`, `GET /knowledge/search`, `GET /audit`, approvals/tickets/escalations/deadletter | ✅ working |
| LangGraph wiring (`app/graph/`) | ✅ compiled graph + runner (interrupt/resume, MemorySaver) |
| pgvector retrieval backend (ADR-002) | ⏳ seam in place (offline lexical default) |
| Real LLM via AI Gateway | ⏳ Day 11 (seam in place) |

## Ticket providers

Select with `TICKET_PROVIDER` (default `mock`, runs with no credentials):

```bash
TICKET_PROVIDER=mock         # in-memory (default)
TICKET_PROVIDER=servicenow   # in-memory ServiceNow stand-in (ADR-003)
TICKET_PROVIDER=jira         # real Jira Cloud — set JIRA_* (see .env.example)
```

Jira needs a free Atlassian Cloud dev site + an API token; if `TICKET_PROVIDER=jira`
but the `JIRA_*` values are missing, the service logs a warning and falls back to
`mock` so it still boots. The Jira adapter is unit-tested with a mocked HTTP
transport, so the full create + idempotency path is verified without a live tenant.

## Setup

```bash
cd services/agent-runtime
python -m venv .venv
# Windows: .venv\Scripts\activate    |  macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"          # core + dev (pytest, ruff)
# Full stack (LLM providers + data stores) for later days:
# pip install -e ".[llm,data,dev]"
```

## Run

```bash
# `python -m` avoids PATH issues on Windows where the uvicorn script isn't exposed
python -m uvicorn app.main:app --reload --port 8088
```

Then open <http://localhost:8088/> for the operations dashboard.

Run a finding through the full pipeline (works with no LLM / no keys):

```bash
# Critical SQLi -> auto-creates a ticket
curl -X POST localhost:8088/analyze -H "content-type: application/json" -d '{
  "finding": {"id":"F-001","ruleId":"formatted-sql-query","title":"SQLi","message":"x",
  "file":"app/api/users.py","cwe":"CWE-89","scannerSeverity":"ERROR",
  "codeSnippet":"q=\"...\"+request.args[\"n\"]; cursor.execute(q)"}}'

# Medium finding -> queued for human approval, then approve it:
curl localhost:8088/approvals
curl -X POST localhost:8088/approvals/<finding_hash>/approve

# Ingest a whole scanner report (Semgrep or SARIF; format auto-detected) and
# run every finding through the pipeline -> returns an outcome summary:
curl -X POST localhost:8088/ingest -H "content-type: application/json" \
  -d "{\"format\":\"auto\",\"report\": $(cat ../../datasets/samples/semgrep-sample.json)}"

# Retrieve grounding knowledge (RAG layer) for a free-text query:
curl "localhost:8088/knowledge/search?q=sql+injection+parameterized+query&k=3"
# /analyze responses now include decision.citations (the OWASP/CWE refs used).

# The governance gate in isolation:
curl -X POST localhost:8088/governance/preview -H "content-type: application/json" \
  -d '{"confidence": 0.95, "recommendedAction": "create_ticket"}'   # -> auto_execute
```

### Compiled LangGraph (conditional routing + checkpointed HITL)

`run_pipeline` runs the same nodes inline (dependency-free fallback); the **compiled
LangGraph** adds explicit state, conditional routing on the disposition, a checkpointer,
and a real **human-approval interrupt** that pauses a run and resumes it in a *later*
request (durable HITL):

```bash
curl localhost:8088/graph                 # nodes + mermaid of the compiled graph

# Medium finding -> the graph PAUSES at the approval gate and returns a threadId:
curl -X POST localhost:8088/graph/analyze -H "content-type: application/json" -d '{
  "finding": {"id":"F-023","ruleId":"cleartext-transmission","title":"HTTP","message":"x",
  "file":"app/clients/partner.py","cwe":"CWE-319","scannerSeverity":"WARNING",
  "codeSnippet":"PARTNER_API=\"http://partner.example.com\""}}'   # -> awaiting_approval

# Resume that paused run with the human's decision (checkpointed by thread_id):
curl -X POST localhost:8088/graph/resume/<thread_id> \
  -H "content-type: application/json" -d '{"approved": true}'      # -> ticket_created
```

### Persistence (Day 10)

State (audit trail, approvals, escalations, dead-letter) and the graph checkpointer sit
behind a seam chosen by `DATABASE_URL`. In-memory is the offline default; point it at
SQLite for durability that survives a restart (Postgres in prod, same schema):

```bash
# Durable local run — approvals + audit survive a restart:
DATABASE_URL=sqlite:///var/secops.db python -m uvicorn app.main:app --port 8088
curl localhost:8088/health      # -> "persistence": "sqlite"
```

`GET /health` reports the active `persistence` backend; `POST /demo/reset` truncates the
stores in place (works for every backend).

### AI Gateway (Day 11)

Every model call goes through one egress (`app/gateway/`): task-aware routing, ordered
fallback (OpenAI → Claude → deterministic), a semantic cache, and cost/latency tracking.
Offline (no keys) it resolves to the deterministic provider — identical analysis output,
$0 cost — while still recording metrics:

```bash
curl localhost:8088/gateway/metrics
# { "totalRequests": 12, "cacheHits": 6, "cacheHitRate": 0.5, "fallbackRate": 0.0,
#   "totalCostUsd": 0.0, "providers": ["deterministic"], "meanLatencyMs": 0.19, ... }
```

Set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` to light up the real providers; the
deterministic provider stays as the final fallback so a provider outage degrades instead
of failing. `GET /health` shows the active `llm.providers`.

### Observability & ops (Day 12)

Three offline-first pillars under `app/observability/`:

```bash
curl localhost:8088/observability/metrics      # Prometheus text exposition (scrape target)
curl localhost:8088/observability/alerts       # firing alerts (escalation/cost/fallback/p95/DLQ)
curl localhost:8088/observability/timeseries   # cost/latency over time (dashboard charts)
curl localhost:8088/observability/traces       # recent spans (pipeline.run -> nodes, llm.complete)
```

- **Tracing** — every pipeline + gateway call is a span (`contextvars`-linked), emitted as a
  structured JSON log; set `OTEL_ENABLED=true` (with the OTel SDK) to export via OTLP.
- **Alerting** — transparent threshold rules (env-overridable: `ALERT_ESCALATION_RATE`,
  `ALERT_FALLBACK_RATE`, `ALERT_P95_LATENCY_MS`, `ALERT_COST_PER_REQUEST_USD`,
  `ALERT_APPROVAL_BACKLOG`); firing alerts show on the dashboard and in `/health`.

### Multi-tenancy & API auth (Day 15)

Off by default — the runtime stays open offline and every request resolves to `DEFAULT_TENANT`
(`public`). Pick another tenant per request with the `X-Tenant-Id` header; each tenant gets its
own isolated audit trail, approvals, tickets, gateway cache/cost, and graph state.

```bash
# Isolation demo (no auth): two tenants never see each other's findings
curl -X POST localhost:8088/demo/seed -H "X-Tenant-Id: acme"
curl localhost:8088/findings -H "X-Tenant-Id: acme"    # acme's findings
curl localhost:8088/findings -H "X-Tenant-Id: globex"  # empty — isolated
```

Turn on enforcement with `AUTH_ENABLED=true`. Authenticate with an API key or a signed HS256 JWT:

```bash
AUTH_ENABLED=true API_KEYS="keyA:acme,keyB:globex" JWT_SECRET=s3cret \
  RATE_LIMIT_RPM=120 python -m uvicorn app.main:app --port 8088

curl localhost:8088/metrics                              # 401 (no creds)
curl localhost:8088/metrics -H "X-API-Key: keyA"         # 200, tenant=acme
curl localhost:8088/metrics -H "Authorization: Bearer <jwt-with-tenant-claim>"
```

`/health`, `/dashboard`, and `/governance/preview` stay open (liveness/demo). Over the
`RATE_LIMIT_RPM` budget a tenant gets `429` with a `Retry-After` header.

### Remediation & SLA tracking (Day 16)

Findings are tracked to closure with per-severity SLA budgets (critical 24h / high 72h /
medium 7d / low 30d). Tickets have a lifecycle; closing one (an external system or a human)
flows back into platform state:

```bash
curl localhost:8088/remediation            # SLA view: per-ticket status + portfolio summary

# Inbound lifecycle sync — resolve a ticket (marks the finding resolved + records audit):
curl -X POST localhost:8088/tickets/<finding_hash>/transition \
  -H "content-type: application/json" -d '{"status": "resolved"}'

# Reconcile findings with any already-resolved tickets (e.g. after polling real Jira):
curl -X POST localhost:8088/remediation/sync
```

`/remediation` returns each ticket's `slaStatus` (on_track / at_risk / breached / resolved),
age, time-to-due, and MTTR for resolved items, plus a summary (open vs resolved, breach/at-risk
counts, SLA compliance, mean MTTR). The dashboard renders this with a one-click **Resolve**.

### Run in Docker (Day 13)

The image is multi-stage and non-root, with a `/health` healthcheck. Build it from the **repo
root** (so `datasets/` is in the build context):

```bash
# From ai-secops-copilot/ :
docker build -f services/agent-runtime/Dockerfile -t secops-agent-runtime .
docker run --rm -p 8088:8088 secops-agent-runtime          # in-memory (offline)
# durable SQLite on a mounted volume:
docker run --rm -p 8088:8088 -e DATABASE_URL=sqlite:////data/secops.db \
  -v secopsdata:/data secops-agent-runtime
```

Or bring up the whole stack (Postgres/pgvector + Redis + runtime + gateway):

```bash
docker compose up -d --build      # dashboard at http://localhost:8088/dashboard
```

`make check` runs the full local gate (lint + tests + eval gate), exactly what CI runs.

## Test

```bash
pytest                # governance (policy + audit), idempotency, analysis, ticketing, pipeline, ingestion, rag, api
ruff check .
```

## Layout

```text
app/
├─ domain.py        # Severity / Action / Disposition enums (single source of truth)
├─ governance.py    # policy engine: thresholds + asymmetric auto-suppress + reason codes
├─ idempotency.py   # finding_hash (duplicate-ticket prevention, ADR-009)
├─ schemas.py       # Pydantic structured-output contract (ADR-010) + citations
├─ ingestion/       # scanner-report adapters: semgrep, sarif, common helpers (ADR-007)
├─ rag/             # knowledge layer: corpus, lexical retriever, pgvector seam (ADR-001/002)
├─ analysis.py      # deterministic finding analysis (the offline LLM stand-in)
├─ prompts.py       # analysis prompt + prompt-injection isolation (ADR-011)
├─ llm.py           # LLMClient seam + analyze_and_validate (bounded re-prompt)
├─ ticketing.py     # orchestration: idempotent contract, approval/escalation/dead-letter/audit
├─ remediation.py   # SLA policy + ticket lifecycle + remediation view/MTTR (Day 16, ADR-018)
├─ providers/       # ticket adapters: mock, jira (real REST v3), servicenow (mock), factory
├─ pipeline.py      # end-to-end run_pipeline (Finding -> RAG -> analysis -> gov -> action)
├─ metrics.py       # dashboard KPI aggregation over the audit trail
├─ gateway/         # AI Gateway egress: router / cache / cost / providers / gateway
├─ observability/   # tracing + time-series + alerts + Prometheus exposition (Day 12)
├─ persistence/     # durable state seam: memory / sqlite_store / checkpointer factory
├─ config.py        # env-driven settings (incl. DATABASE_URL backend selection)
├─ auth.py          # API-key + HS256 JWT auth, tenant resolution (Day 15, ADR-017)
├─ ratelimit.py     # per-tenant fixed-window rate limiter (Day 15)
├─ tenancy.py       # TenantRegistry: isolated per-tenant state/provider/gateway/graph
├─ main.py          # FastAPI app (/graph, /dashboard, /metrics, /analyze, /ingest, ...)
├─ static/          # single-page operations dashboard (served at /dashboard)
└─ graph/           # LangGraph: state, nodes, build (compiled graph), runner (HITL+checkpoint)
tests/              # unit + end-to-end tests
```

Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep output).
