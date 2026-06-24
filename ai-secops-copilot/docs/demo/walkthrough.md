# End-to-End Demo Walkthrough (Day 14)

A single, reproducible run of the whole platform — **offline, no API keys, no server, no
network**. It drives the agent runtime in-process (FastAPI `TestClient`) over the bundled
Semgrep + SARIF sample reports and narrates each stage of the lifecycle.

## Run it

```bash
# from the repo root (ai-secops-copilot/)
python scripts/demo_walkthrough.py            # narrated run (below)
python scripts/demo_walkthrough.py --quiet    # just the section headers
make demo                                      # same thing via the Makefile
```

The script exits non-zero if any step fails, so it doubles as an end-to-end smoke test.
It needs only the agent-runtime installed (`cd services/agent-runtime && pip install -e ".[dev]"`).

## What the run proves

| Stage | What a reviewer sees |
| --- | --- |
| **1. Health** | Everything wired offline: mock ticketing, in-memory persistence, LangGraph orchestration, gateway LLM egress (deterministic provider), in-process tracing, governance thresholds. |
| **2. Reset + seed** | Two scanner reports normalized (ADR-007) and driven through the full pipeline. |
| **3. Findings** | Current-state view (deduped by `finding_hash`): a critical SQLi **auto-tickets**, a medium **waits for approval**, clear false positives are **auto-suppressed**, an ambiguous critical **escalates**. |
| **4. Human-in-the-loop** | A human approves the pending finding → the ticket is created (`actor=human`). |
| **5. Idempotency** | Re-seeding the same reports: the append-only **audit events grow**, but **findings and tickets do not** (idempotent by `finding_hash`). |
| **6. KPIs** | Autonomy split (automation / approval / escalation) + latency, aggregated from the audit trail. |
| **7. AI Gateway** | Single LLM egress with a semantic cache — re-seeding identical findings yields a **50% cache hit rate at $0** (deterministic provider, offline). |
| **8. Observability** | The alert rule engine reports **0 firing alerts** offline, plus a valid Prometheus scrape target. |
| **9. Audit trail** | The append-only "why": disposition + machine-readable `reasonCode` + actor for every decision. |

> Note: timing numbers (latency, span durations) vary run-to-run; everything else
> (dispositions, counts, cache-hit rate, alerts) is deterministic.

## Recorded run

```text
========================================================================
1. HEALTH — what's wired (all offline, no keys)
========================================================================
  service        : agent-runtime v0.1.0 (development)
  ticketProvider : mock
  persistence    : memory
  orchestration  : langgraph
  llm egress     : gateway (providers=['deterministic'], cache=True)
  observability  : tracing=in-process, alertsFiring=0
  governance     : auto>=0.9 suppress>=0.95

========================================================================
2. RESET + SEED — ingest the bundled Semgrep + SARIF reports
========================================================================
  seeded reports : semgrep-sample.json, sarif-sample.json
    semgrep-sample.json    {'ticket_created': 1, 'suppressed': 1, 'pending_approval': 1, 'escalated': 1}
    sarif-sample.json      {'ticket_created': 1, 'suppressed': 1}

========================================================================
3. FINDINGS — current-state view (deduped by finding_hash)
========================================================================
  6 findings (one row per finding; the audit log keeps every event)

  finding             severity  disposition     outcome           ticket
  ----------------------------------------------------------------------------
  sarif-6710414f10    info      auto_execute    suppressed        -
  sarif-a94fe43deb    critical  auto_execute    ticket_created    mock:SEC-2
  sg-a28bc19763       critical  escalate        escalated         -
  sg-c72fcf4ce7       info      auto_execute    suppressed        -
  sg-042d452933       medium    human_approval  pending_approval  (pending)
  sg-48e4811ba2       critical  auto_execute    ticket_created    mock:SEC-1

========================================================================
4. HUMAN-IN-THE-LOOP — approve the pending finding -> ticket created
========================================================================
  pending: sg-042d452933 (confidence=0.78, human_approval)
  approved by human -> ticket_created: mock:SEC-3 (open)

========================================================================
5. IDEMPOTENCY — re-seed the same reports (events grow, findings don't)
========================================================================
  findingsProcessed : 6 -> 6  (unchanged: deduped)
  decisionEvents    : 7 -> 13  (grows: append-only audit log)
  ticketsCreated    : 3 -> 3  (unchanged: idempotent by finding_hash)

========================================================================
6. KPIs — autonomy split + latency
========================================================================
  findings processed : 6
  tickets created    : 3
  pending approvals  : 1
  escalations        : 1
  automation rate    : 67%
  approval rate      : 17%
  escalation rate    : 17%
  latency (mean/p95) : 0.65 / 0.93 ms

========================================================================
7. AI GATEWAY — single LLM egress (cache + cost)
========================================================================
  configured       : ['deterministic']  (deterministic always-on fallback)
  requests         : 12
  cache hits       : 6  (50% hit rate)
  fallbacks used   : 0  (0% rate)
  total cost (USD) : 0.0  (offline -> free)

========================================================================
8. OBSERVABILITY — alert rule engine over governance/cost/reliability
========================================================================
  0 alerts firing — healthy (no escalation spike, no dead-letters, costs nominal)
  Prometheus scrape : 200 (48 lines of text exposition at /observability/metrics)

========================================================================
9. AUDIT TRAIL — append-only 'why' (last 6 events)
========================================================================
  13 total events (compliance log)

  finding             disposition     reasonCode                      actor
  ----------------------------------------------------------------------------
  sg-48e4811ba2       auto_execute    auto_high_confidence            system
  sg-c72fcf4ce7       auto_execute    auto_suppress_high_confidence   system
  sg-042d452933       human_approval  approval_band                   system
  sg-a28bc19763       escalate        model_escalation                system
  sarif-a94fe43deb    auto_execute    auto_high_confidence            system
  sarif-6710414f10    auto_execute    auto_suppress_high_confidence   system

========================================================================
DEMO COMPLETE
========================================================================
  Ran the full lifecycle offline: ingest -> RAG-grounded analysis -> governed
  decision -> action (auto / human-approval / escalate) -> metrics, gateway,
  alerts, and an auditable trail — deterministically, with zero external calls.

  Live version: `python -m uvicorn app.main:app --port 8088` then open
  http://localhost:8088/ for the operations dashboard.
```

## The live version

For a visual demo, run the server and open the dashboard:

```bash
cd services/agent-runtime
python -m uvicorn app.main:app --port 8088
# open http://localhost:8088/  → KPI cards, autonomy split, audit trail,
#   pending-approvals panel (approve/reject), gateway panel, alerts banner
```

Click **Run demo** (→ `POST /demo/seed`) to play the same story, **Reset** to clear it.
The whole stack (Postgres/pgvector + Redis + both services) also runs with one command:
`docker compose up --build` (see [ADR-016](../architecture-decisions.md)).
