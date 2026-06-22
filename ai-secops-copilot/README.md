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
│  └─ schema/security-findings-v1.schema.json  # JSON Schema for the dataset
├─ evals/                          # Evaluation harness
│  ├─ run_eval.py                  # CLI: load → predict → score → report → gate
│  ├─ metrics.py                   # accuracy, confusion matrix, P/R/F1 (stdlib)
│  └─ predictors.py                # heuristic baseline (+ runtime predictor stub)
├─ services/
│  ├─ gateway/                     # NestJS control plane + AI Gateway (single LLM egress)
│  └─ agent-runtime/               # Python LangGraph agent runtime
├─ infra/postgres/init.sql         # enables pgvector
└─ scripts/                        # run-checks.ps1 / run-checks.sh
```

## Status

Vision, architecture, scope, and decisions are **locked**.

**Day 1 complete:** golden dataset (50 labeled findings) + runnable eval harness
(heuristic baseline: 86% severity accuracy, 100%/37.5% FP precision/recall) +
hybrid scaffold (Python LangGraph runtime with a working governance gate &
idempotency; NestJS AI Gateway with provider fallback + cost/latency metrics).

**Next — Day 2:** walking skeleton end-to-end (Finding → LLM → recommendation →
approval → mock Jira) with structured-output validation, then swap the eval's
`heuristic` predictor for the `runtime` predictor to capture the before/after delta.

## Documentation

- [Product Vision](docs/PRODUCT_VISION.md)
- [Architecture Decisions](docs/architecture-decisions.md)
- [Architecture Diagrams](docs/diagrams/architecture.md)
- [Build Plan & Notes](docs/planning/AI_PLATFORM_ENGINEER_PREP.md)
- [Interview & Profile Prep](docs/planning/interview-prep.md)

---

Security-domain modeling is implemented clean-room from public standards (SARIF, OWASP, CWE, Semgrep
public output). No proprietary code, schema, data, or credentials are used.
