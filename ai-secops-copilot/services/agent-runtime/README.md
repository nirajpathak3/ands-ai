# Agent Runtime (Python + LangGraph)

The orchestration core of the AI Security Operations Copilot. Models the locked
flow as a LangGraph state graph:

```text
ingest -> Finding Analysis Node -> Ticket Decision Node -> Governance Gate -> END
```

- **Finding Analysis Node** — analyzes a finding into `{severity, confidence, reason, recommendedAction}` (calls the AI Gateway; validates structured output). *Day-2 stub today.*
- **Ticket Decision Node + Governance Gate** — maps confidence → disposition (auto-execute / human-approval / escalate). **Implemented.**

## Status (Day 1 scaffold)

| Piece | State |
| --- | --- |
| Domain enums, governance, idempotency, schemas | ✅ implemented + unit-tested |
| `GET /health`, `POST /governance/preview` | ✅ working |
| `POST /analyze` (full graph) | ⏳ 501 until Day 2 |
| LangGraph wiring (`app/graph/`) | ✅ structure; analysis node stubbed |

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

Try the governance gate (works with no LLM / no keys):

```bash
curl -X POST localhost:8088/governance/preview -H "content-type: application/json" \
  -d '{"confidence": 0.95, "recommendedAction": "create_ticket"}'   # -> auto_execute
curl -X POST localhost:8088/governance/preview -H "content-type: application/json" \
  -d '{"confidence": 0.71, "recommendedAction": "create_ticket"}'   # -> human_approval
```

## Test

```bash
pytest                # governance + idempotency unit tests (no heavy deps needed)
ruff check .
```

## Layout

```text
app/
├─ domain.py        # Severity / Action / Disposition enums (single source of truth)
├─ governance.py    # confidence-gated, two-threshold -> three-disposition gate
├─ idempotency.py   # finding_hash (duplicate-ticket prevention, ADR-009)
├─ schemas.py       # Pydantic structured-output contract (ADR-010)
├─ config.py        # env-driven settings
├─ main.py          # FastAPI app
└─ graph/           # LangGraph: state, nodes, build
tests/              # unit tests
```

Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep output).
