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

**Next — Day 4:** Semgrep finding ingestion (map real scanner output to the
normalized finding contract).

## Documentation

- [Product Vision](docs/PRODUCT_VISION.md)
- [Architecture Decisions](docs/architecture-decisions.md)
- [Architecture Diagrams](docs/diagrams/architecture.md)
- [Build Plan & Notes](docs/planning/AI_PLATFORM_ENGINEER_PREP.md)
- [Interview & Profile Prep](docs/planning/interview-prep.md)

---

Security-domain modeling is implemented clean-room from public standards (SARIF, OWASP, CWE, Semgrep
public output). No proprietary code, schema, data, or credentials are used.
