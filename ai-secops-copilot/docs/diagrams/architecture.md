# Architecture Diagrams — AI Security Operations Copilot

> **Target vs as-built.** Sections 1–8 show the **target** architecture (the full product
> vision: NestJS egress, Langfuse, managed providers). Section 9 shows the **as-built runtime
> as of Day 14** — what actually runs today: an in-process Python AI Gateway, an in-process
> observability stack (tracer + Prometheus exposition + alert engine, optional OpenTelemetry),
> pluggable persistence (memory → SQLite → Postgres), and a deterministic offline fallback so
> the whole system runs with no keys. Where the two differ, the as-built diagram is authoritative.

---

## 1. Full System Architecture

Shows every component and how they connect. The AI Gateway sits before the LLM — it is the
single egress point for all model calls.

```mermaid
flowchart LR
    subgraph input [Input Layer]
        SG[Semgrep / SARIF]
        API[NestJS API Gateway]
    end

    subgraph runtime [Agent Runtime — Python / LangGraph]
        AN[Finding Analysis Node]
        RAG[RAG Knowledge Layer]
        DN[Ticket Decision Node]
        GG[Governance Gate]
    end

    subgraph knowledge [Knowledge Store]
        OW[(OWASP Top 10)]
        CW[(CWE)]
        CV[(CVE / Runbooks)]
        PG[(pgvector — Postgres)]
    end

    subgraph gateway [AI Gateway — NestJS]
        GW[Model Router]
        SC[Semantic Cache — Redis]
        CT[Cost / Latency Tracker]
    end

    subgraph models [LLM Providers]
        OA[OpenAI — primary]
        AN2[Claude — fallback]
    end

    subgraph tools [MCP Tool Layer]
        JR[Jira MCP — real]
        SN[ServiceNow MCP — mock]
    end

    subgraph observe [Observability]
        LF[Langfuse]
        OT[OpenTelemetry]
        DB[Dashboard]
    end

    SG --> API
    API --> AN
    AN --> RAG
    RAG --> OW & CW & CV
    OW & CW & CV --> PG
    PG --> AN
    AN --> GW
    GW --> SC
    GW --> CT
    GW --> OA
    GW --> AN2
    AN --> DN
    DN --> GG
    GG -->|confidence >= 0.90| AUTO[Auto Execute]
    GG -->|0.60 <= c < 0.90| APPR[Human Approval]
    GG -->|confidence < 0.60| ESC[Escalate]
    AUTO --> JR
    APPR --> JR
    JR --> SN
    CT --> LF
    JR --> LF
    LF --> OT
    OT --> DB
```

---

## 2. End-to-End Request Flow

The path a single finding takes from ingestion to Jira ticket.

```mermaid
sequenceDiagram
    participant SC as Scanner (Semgrep)
    participant GW as NestJS Gateway
    participant AN as Analysis Node
    participant RAG as RAG Layer
    participant LLM as AI Gateway → LLM
    participant GG as Governance Gate
    participant MCP as Jira MCP
    participant LF as Langfuse

    SC->>GW: POST /findings (SARIF JSON)
    GW->>GW: validate + dedupe (finding_hash)
    GW->>AN: run graph with finding state
    AN->>RAG: embed finding → retrieve OWASP/CWE chunks
    RAG-->>AN: top-k knowledge context
    AN->>LLM: prompt (finding + context) → structured output
    LLM->>LLM: route → cache check → OpenAI / Claude
    LLM-->>AN: AnalysisResult {severity, confidence, reason}
    LLM->>LF: log tokens, latency, cost
    AN->>GG: pass confidence score
    alt confidence >= 0.90
        GG->>MCP: createIssue(payload)
        MCP-->>GG: ticket_id
    else 0.60 <= confidence < 0.90
        GG-->>GW: approval_required event
        GW-->>SC: 202 Accepted — pending approval
    else confidence < 0.60
        GG-->>GW: escalate event
    end
    MCP->>LF: log ticket action + result
    LF->>LF: update metrics (automation_rate, approval_rate)
```

---

## 3. Governance Gate — Confidence Flow

```mermaid
flowchart TD
    C{Confidence Score}
    C -->|">= 0.90 — high"| A[AUTO-EXECUTE\nJira ticket created immediately]
    C -->|"0.60 – 0.89 — medium"| H[HUMAN APPROVAL\nanalyst notified, waits for confirm]
    C -->|"< 0.60 — low"| E[ESCALATE\nrequires senior review]

    A --> LOG[Audit log + Langfuse metric]
    H --> WAIT[Approval queue]
    WAIT -->|approved| LOG
    WAIT -->|rejected| REJ[Rejected — log reason]
    E --> LOG
```

---

## 4. LangGraph — Agent State Flow

```mermaid
stateDiagram-v2
    [*] --> FindingReceived
    FindingReceived --> IdempotencyCheck
    IdempotencyCheck --> AlreadyProcessed: hash exists
    IdempotencyCheck --> FindingAnalysisNode: new finding
    AlreadyProcessed --> [*]

    FindingAnalysisNode --> RAGRetrieval: fetch knowledge
    RAGRetrieval --> LLMCall: prompt + context
    LLMCall --> OutputValidation: Pydantic schema
    OutputValidation --> RepromptOnce: validation fail
    RepromptOnce --> OutputValidation
    OutputValidation --> TicketDecisionNode: valid result

    TicketDecisionNode --> GovernanceGate
    GovernanceGate --> AutoExecute: high confidence
    GovernanceGate --> ApprovalQueue: medium confidence
    GovernanceGate --> EscalateQueue: low confidence

    AutoExecute --> JiraMCP
    ApprovalQueue --> AwaitApproval
    AwaitApproval --> JiraMCP: approved
    AwaitApproval --> Rejected: rejected

    JiraMCP --> RetryOnFail: Jira error
    RetryOnFail --> JiraMCP: retry 1-3
    RetryOnFail --> DeadLetterQueue: max retries hit

    JiraMCP --> MetricsEmit
    MetricsEmit --> [*]
```

---

## 5. Failure Handling Paths

```mermaid
flowchart TD
    subgraph llm [LLM Failure]
        L1[LLM timeout] --> L2[Retry with backoff]
        L2 --> L3{Retry ok?}
        L3 -->|yes| L4[Continue]
        L3 -->|no| L5[Claude fallback]
        L5 --> L6{Fallback ok?}
        L6 -->|no| L7[Escalate finding]
    end

    subgraph out [Bad Output]
        O1[Invalid JSON / schema] --> O2[Re-prompt once with error]
        O2 --> O3{Valid?}
        O3 -->|yes| O4[Continue]
        O3 -->|no| O5[Escalate — do not execute tool]
    end

    subgraph jira [Jira Failure]
        J1[Jira API error] --> J2[Retry 1-3x backoff]
        J2 --> J3{Ok?}
        J3 -->|yes| J4[Ticket created]
        J3 -->|no| J5[Dead Letter Queue]
        J5 --> J6[Alert + manual review]
    end

    subgraph dup [Duplicate Prevention]
        D1[Incoming finding] --> D2[Compute finding_hash]
        D2 --> D3{Hash seen?}
        D3 -->|yes| D4[Skip — return existing ticket_id]
        D3 -->|no| D5[Process normally]
    end
```

---

## 6. Evaluation Pipeline Flow

```mermaid
flowchart LR
    GD[Golden Dataset\n50 labeled findings] --> RUN[run_eval.py]
    RUN --> PRED[Run each finding\nthrough agent]
    PRED --> CMP[Compare prediction\nvs label]

    CMP --> M1[Severity Accuracy]
    CMP --> M2[Ticket Action Accuracy]
    CMP --> M3[FP Precision / Recall / F1]
    CMP --> M4[LLM-as-Judge\nroot cause quality]

    M1 & M2 & M3 & M4 --> SCORE[Overall Eval Score]
    SCORE --> GATE{Score >= threshold?}
    GATE -->|pass| MERGE[Safe to merge / ship]
    GATE -->|fail| BLOCK[Block — show regression diff]
```

---

## 7. Hybrid Deployment Topology

Shows how the two services talk to each other and to shared infra.

```mermaid
flowchart TB
    subgraph ts [TypeScript — NestJS]
        API2[Findings API\nPOST /findings]
        GW2[AI Gateway\nrouting · cache · cost]
        MCP2[MCP Tool Layer\nJira / ServiceNow]
        DASH2[Dashboard API]
    end

    subgraph py [Python — LangGraph]
        GRAPH[Agent Graph\nAnalysis → Decision → Gate]
        EVAL[Eval Harness\nrun_eval.py]
        RAG2[RAG Service\nembed · retrieve · rank]
    end

    subgraph data [Shared Data]
        PG2[(Postgres + pgvector)]
        RED[(Redis\nsemantic cache · state)]
    end

    subgraph obs [Observability]
        LF2[Langfuse\nLLM traces]
        OT2[OpenTelemetry\nservice spans]
    end

    API2 -->|HTTP| GRAPH
    GRAPH --> GW2
    GRAPH --> RAG2
    RAG2 --> PG2
    GW2 --> RED
    GRAPH --> RED
    GW2 --> OA2[OpenAI]
    GW2 --> CL2[Claude]
    GRAPH --> MCP2
    MCP2 --> JIRA[Jira API]
    GW2 --> LF2
    MCP2 --> LF2
    LF2 --> OT2
    OT2 --> DASH2
```

---

## 8. Career Narrative — How the projects connect

For interviews: shows you built a *platform*, not isolated demos.

```mermaid
flowchart LR
    subgraph existing [Existing Projects — Reused Patterns]
        OBS[obs-agent\nHITL governance\nconfidence gating\naudit trail\nNestJS DDD]
        VEHO[veho-platform\nblackboard state\ngate workflows\nmulti-agent design]
    end

    subgraph copilot [AI Security Ops Copilot — Flagship]
        CORE[LangGraph runtime\nFinding Analysis\nTicket Decision\nGovernance Gate]
        RAGC[RAG Layer\npgvector · OWASP · CWE]
        GWAYC[AI Gateway\nNestJS · routing\ncache · cost]
        EVALC[Eval Harness\ngolden dataset\naccuracy · F1\nregression gate]
        MCPC[MCP Tools\nJira · ServiceNow]
    end

    OBS -->|governance pattern| CORE
    VEHO -->|agent state & gates| CORE
    CORE --> RAGC
    CORE --> GWAYC
    CORE --> EVALC
    CORE --> MCPC
```

---

## 9. As-Built Runtime (Day 14)

What actually runs today. Everything in the `agent-runtime` box is **in-process Python**, so the
whole platform runs offline with no keys (the deterministic provider is the always-on fallback).
The NestJS gateway is the equivalent standalone control-plane (same `llm.types.ts`/`cost.ts`
contract); real providers, OTel export, and Postgres/Redis light up by configuration only.

```mermaid
flowchart TB
    subgraph ingest [Ingestion]
        RPT[Semgrep / SARIF report]
        NORM[normalize → Finding contract\nADR-007]
    end

    subgraph rt [agent-runtime — Python / FastAPI, in-process]
        direction TB
        subgraph graph [LangGraph — compiled StateGraph]
            FA[finding_analysis\nstructured output + reprompt]
            TD[ticket_decision]
            GG{Governance Gate\nasymmetric thresholds}
            AW[await_approval\nHITL interrupt + resume]
        end
        RAG[RAG retriever\nlexical TF-IDF · pgvector seam]
        GWAY[AI Gateway\nroute · semantic cache · fallback · cost]
        TKT[Ticketing orchestrator\nidempotent by finding_hash]
        OBS[Observability\ntracer · time-series · alert engine]
    end

    subgraph providers [LLM providers — ordered fallback]
        OAI[OpenAI]
        CLA[Claude]
        DET[Deterministic\nalways-on, offline, $0]
    end

    subgraph tools [Ticket providers]
        MOCK[Mock - default]
        JIRA[Jira Cloud - real]
        SNOW[ServiceNow - mock]
        DLQ[(Dead-letter queue)]
    end

    subgraph state [Persistence seam — DATABASE_URL]
        MEM[(in-memory\ndefault)]
        SQL[(SQLite\nlocal/CI)]
        PGS[(Postgres\nprod)]
    end

    subgraph egress [Observability egress - optional]
        OTLP[OpenTelemetry OTLP\nOTEL_ENABLED=true]
        PROM[Prometheus scrape\n/observability/metrics]
        DASH[Dashboard + /health]
    end

    RPT --> NORM --> FA
    FA --> RAG
    RAG --> FA
    FA --> GWAY
    GWAY --> OAI --> CLA --> DET
    FA --> TD --> GG
    GG -->|auto-execute / escalate| TKT
    GG -->|approval band| AW
    AW -->|approved| TKT
    TKT --> MOCK & JIRA & SNOW
    TKT -.->|provider failure| DLQ
    GG --> OBS
    GWAY --> OBS
    rt --- state
    OBS --> OTLP & PROM & DASH
```

### Drift from the target diagrams (1–8)

| Concern | Target (1–8) | As-built (Day 14) |
| --- | --- | --- |
| LLM egress | NestJS gateway service | **In-process Python gateway**; NestJS is the standalone control-plane scaffold |
| Providers | OpenAI primary, Claude fallback | OpenAI → Claude → **deterministic** (offline, always-on final fallback) |
| Semantic cache | Redis (cosine) | **Lexical Jaccard** in-process offline; Redis/cosine is the prod upgrade behind the same seam |
| LLM tracing | Langfuse | **In-process tracer** + structured JSON logs; **OpenTelemetry OTLP** is the opt-in export (Langfuse not built) |
| Metrics | Langfuse dashboards | **Prometheus** text exposition + rolling time-series + **alert rule engine** |
| Vector store | pgvector (required) | **Lexical retriever** default; pgvector behind the `KnowledgeRetriever` seam |
| State | Postgres | **memory → SQLite → Postgres** via `DATABASE_URL` (identical SQL schema) |
| Run | — | `python scripts/demo_walkthrough.py` (offline) · `docker compose up` (full stack) |
