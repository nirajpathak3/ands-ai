# Gateway (NestJS + TypeScript)

The control plane and **AI Gateway** for the AI Security Operations Copilot.
It is the single egress for all LLM calls (ADR-006) and the ingress for findings.

## Responsibilities

- **AI Gateway** (`src/gateway/`) — single LLM egress: ordered provider fallback
  (OpenAI primary → Claude fallback), cost/latency/token tracking, semantic-cache
  hook. Apps never call providers directly.
- **Findings ingress** (`src/findings/`) — validate a finding at the edge
  (`class-validator`), then forward to the Python agent runtime.
- **Health** (`src/health/`) — liveness + safe config snapshot (reports key
  *presence*, never values).

## Status (Day 1 scaffold)

| Piece | State |
| --- | --- |
| App bootstrap, config, health, DI wiring | ✅ working |
| Gateway fallback orchestration + cost/latency metrics | ✅ implemented + unit-tested (`gateway.service.spec.ts`) |
| Provider SDK calls (OpenAI/Claude) | ⏳ stubbed until Day 11 |
| `POST /findings/analyze` → agent-runtime | ✅ forwards (runtime returns 501 until Day 2) |

## Setup & run

```bash
cd services/gateway
cp .env.example .env        # Windows: copy .env.example .env
npm install
npm run start:dev           # http://localhost:3000
```

## Test

```bash
npm test                    # gateway fallback + metrics unit tests
npm run lint
```

## Key endpoints

| Method | Path                | Purpose                                            |
| ------ | ------------------- | -------------------------------------------------- |
| GET    | `/`                 | name + status                                      |
| GET    | `/health`           | liveness + config presence + provider readiness    |
| GET    | `/gateway/metrics`  | cost / latency / token / fallback counters         |
| POST   | `/findings/analyze` | validate finding → forward to agent runtime         |

## Layout

```text
src/
├─ main.ts                 # bootstrap (global validation pipe)
├─ app.module.ts
├─ config/configuration.ts # typed env config
├─ health/                 # health controller
├─ gateway/                # AI Gateway: providers, fallback, cost, metrics
│  ├─ gateway.service.ts   # ordered fallback + observability (the core)
│  ├─ cost.ts              # token → USD estimation
│  └─ providers/           # openai (primary), anthropic (fallback)
└─ findings/               # ingress DTO + controller + runtime bridge
```

Clean-room: all security modeling is from public standards (SARIF, OWASP, CWE, Semgrep output).
