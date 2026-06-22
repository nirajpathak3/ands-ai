# Agent Runtime (Python + LangGraph)

The orchestration core of the AI Security Operations Copilot. Models the locked
flow end to end:

```text
ingest (idempotency hash) -> Finding Analysis Node -> Ticket Decision Node
  -> Governance Gate -> execute (auto-ticket | approval queue | escalate)
```

- **Finding Analysis Node** — analyzes a finding into `{severity, confidence, reason, recommendedAction}` through the `LLMClient` seam and **validates the structured output** (Pydantic) before anything acts on it, bounded-retrying on invalid output (ADR-010). Finding text is treated as untrusted input, isolated from instructions (ADR-011). **Implemented.**
- **Ticket Decision Node + Governance Gate** — maps confidence → disposition (auto-execute / human-approval / escalate). **Implemented.**
- **Ticketing + HITL** — idempotent mock ticket provider, human-approval queue, escalation queue (ADR-009). Real Jira / ServiceNow mock arrive Day 3. **Implemented.**

> **The LLM is a deterministic offline stand-in today** (`app/analysis.py` via
> `DeterministicLLM`), so the whole pipeline runs with no API keys and is fully
> reproducible in CI. On Day 11 the AI Gateway swaps a real model in behind the
> same `LLMClient` seam — nothing downstream changes.

## Status (Day 2 — walking skeleton complete)

| Piece | State |
| --- | --- |
| Domain enums, governance, idempotency, schemas | ✅ implemented + unit-tested |
| Finding analysis (deterministic LLM stand-in) + structured-output validation | ✅ implemented + tested |
| Mock ticketing, HITL approval queue, escalation queue | ✅ implemented + tested |
| `POST /analyze` (full end-to-end pipeline) | ✅ working |
| `GET /health`, `POST /governance/preview`, approvals/tickets/escalations | ✅ working |
| LangGraph wiring (`app/graph/`) | ✅ nodes implemented (full graph upgrade Day 9) |
| Real LLM via AI Gateway | ⏳ Day 11 (seam in place) |

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

# The governance gate in isolation:
curl -X POST localhost:8088/governance/preview -H "content-type: application/json" \
  -d '{"confidence": 0.95, "recommendedAction": "create_ticket"}'   # -> auto_execute
```

## Test

```bash
pytest                # 34 tests: governance, idempotency, analysis, ticketing, pipeline
ruff check .
```

## Layout

```text
app/
├─ domain.py        # Severity / Action / Disposition enums (single source of truth)
├─ governance.py    # confidence-gated, two-threshold -> three-disposition gate
├─ idempotency.py   # finding_hash (duplicate-ticket prevention, ADR-009)
├─ schemas.py       # Pydantic structured-output contract (ADR-010)
├─ analysis.py      # deterministic finding analysis (the offline LLM stand-in)
├─ prompts.py       # analysis prompt + prompt-injection isolation (ADR-011)
├─ llm.py           # LLMClient seam + analyze_and_validate (bounded re-prompt)
├─ ticketing.py     # idempotent mock tickets + HITL approval + escalation queues
├─ pipeline.py      # end-to-end run_pipeline (Finding -> analysis -> gov -> action)
├─ config.py        # env-driven settings
├─ main.py          # FastAPI app (/analyze, /approvals, /tickets, /escalations)
└─ graph/           # LangGraph: state, nodes, build
tests/              # unit + end-to-end tests
```

Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep output).
