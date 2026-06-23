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

> **The LLM is a deterministic offline stand-in today** (`app/analysis.py` via
> `DeterministicLLM`), so the whole pipeline runs with no API keys and is fully
> reproducible in CI. On Day 11 the AI Gateway swaps a real model in behind the
> same `LLMClient` seam — nothing downstream changes.

## Status (Day 8 — demo milestone: operations dashboard)

| Piece | State |
| --- | --- |
| **Operations dashboard** (`GET /` → `/dashboard`, KPIs + audit + approvals, one-click seed) | ✅ implemented + tested |
| **Metrics** (`GET /metrics`: automation/approval/escalation rates, latency) | ✅ implemented + tested |
| Governance policy engine (asymmetric auto-suppress bar, reason codes) | ✅ implemented + unit-tested |
| Audit trail (`GET /audit`: who/what/why per decision) | ✅ implemented + tested |
| Ingestion: Semgrep JSON + SARIF v2.1.0 -> finding contract | ✅ implemented + tested |
| RAG: OWASP/CWE corpus + lexical retriever + citations | ✅ implemented + tested |
| Finding analysis (deterministic LLM stand-in) + structured-output validation | ✅ implemented + tested |
| Ticketing adapters: mock, **real Jira (REST v3)**, ServiceNow mock | ✅ implemented + tested |
| Idempotent create (in-memory map / Jira label search), dead-letter on failure | ✅ implemented + tested |
| HITL approval queue, escalation queue | ✅ implemented + tested |
| `GET /dashboard`, `GET /metrics`, `POST /demo/seed`, `POST /analyze`, `POST /ingest`, `GET /knowledge/search`, `GET /audit`, approvals/tickets/escalations/deadletter | ✅ working |
| LangGraph wiring (`app/graph/`) | ✅ nodes implemented (full graph upgrade Day 9) |
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
uvicorn app.main:app --reload --port 8088
```

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
├─ providers/       # ticket adapters: mock, jira (real REST v3), servicenow (mock), factory
├─ pipeline.py      # end-to-end run_pipeline (Finding -> RAG -> analysis -> gov -> action)
├─ metrics.py       # dashboard KPI aggregation over the audit trail
├─ config.py        # env-driven settings
├─ main.py          # FastAPI app (/dashboard, /metrics, /demo/seed, /analyze, /ingest, ...)
├─ static/          # single-page operations dashboard (served at /dashboard)
└─ graph/           # LangGraph: state, nodes, build
tests/              # unit + end-to-end tests
```

Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep output).
