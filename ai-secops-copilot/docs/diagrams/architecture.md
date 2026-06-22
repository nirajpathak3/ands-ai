# Architecture Diagrams — AI Security Operations Copilot

## System Architecture (AI Gateway as single LLM egress)

```mermaid
flowchart LR
    A[Semgrep Findings] --> B[Finding Analysis Node]
    B --> C[AI Gateway]
    C --> D[OpenAI]
    C --> E[Claude Fallback]
    B --> F[RAG Knowledge Layer]
    F --> G[(OWASP)]
    F --> H[(CWE)]
    F --> I[(Historical Findings)]
    F --> J[Ticket Decision Node]
    J --> K[Governance Gate]
    K -->|High Confidence| L[Auto Execute]
    K -->|Medium Confidence| M[Human Approval]
    K -->|Low Confidence| N[Escalate]
    L --> O[Jira MCP]
    M --> O
    O --> P[Metrics & Evaluation]
    C --> Q[Langfuse + OTel]
    P --> Q
    Q --> R[Dashboard]
```

## System Flow (the single user flow that matters)

```mermaid
flowchart TD
    F1[Security Finding] --> F2[Finding Analysis]
    F2 --> F3[Confidence Score]
    F3 --> F4[Governance Decision]
    F4 -->|High| F5[Auto Execute]
    F4 -->|Medium| F6[Human Approval]
    F5 --> F7[Jira Ticket]
    F6 --> F7
    F7 --> F8[Metrics + Evaluation]
```

## Governance Model (two thresholds → three dispositions)

```mermaid
flowchart TD
    C{confidence} -->|">= autoThreshold (0.90)"| A[AUTO-EXECUTE]
    C -->|"suggest <= c < auto"| H[HUMAN APPROVAL]
    C -->|"< suggestThreshold (0.60)"| E[ESCALATE / REVIEW]
```

## Hybrid Deployment Topology

```mermaid
flowchart LR
    subgraph cp [Control Plane - NestJS/TS]
      GW[AI Gateway + API]
      DASH[Dashboard]
    end
    subgraph ar [Agent Runtime - Python/LangGraph]
      GRAPH[Analysis + Decision Graph]
      EVAL[Eval Harness]
    end
    subgraph data [Data]
      PG[(Postgres + pgvector)]
      REDIS[(Redis cache)]
    end
    GW --> GRAPH
    GRAPH --> PG
    GW --> REDIS
    GRAPH --> GW
    GW --> LF[Langfuse + OTel]
```
