# Demo walkthrough — vision in, scaffolded product repo out

A recorded run of the offline-deterministic vertical slice. One command takes a product
**vision** and drives the whole product-development lifecycle — plan → Discovery (in
parallel) → PRD → UX (personas + flows + a rendered HTML mockup) → architecture (API/DB) →
a real scaffolded repo on disk — pausing at each **HITL gate**, gating every artifact on
**eval-as-gate**, and recording the full **cost + audit trail**.

It runs with **no API keys, no network, and $0 cost**, and is byte-for-byte reproducible
(the unified agent echoes a deterministic seed through the AI Gateway). Set
`FORGE_MODE=live` + a provider key to run the *same* flow against real models.

```bash
# Fully offline, deterministic — doubles as a smoke test (exits non-zero on failure):
python scripts/demo_walkthrough.py
# Try your own brief:
python scripts/demo_walkthrough.py --vision "your product idea"
```

> The recording below is verbatim console output from
> `python scripts/demo_walkthrough.py` (default vision).

---

## Recorded run

### 1. Blueprint — the product-development program (loaded as data)

The lifecycle is **data**, not code: a DAG of stages → artifacts → owning role → gate
materiality. Swap the blueprint + skill packs and the *same* kernel builds a different kind
of project.

```text
  [0] Vision Intake & Plan     gate=always-human  :: vision_brief
  [1] Discovery                gate=auto-if-eval  :: user_research, competitive_analysis, business_case
  [2] Strategy / PRD           gate=always-human  :: prd, ai_capability_map
  [3] UX                       gate=always-human  :: personas, user_flows, mockup
  [4] Technical Architecture   gate=auto-if-eval  :: system_architecture, api_spec, db_schema
  [5] Repo Scaffold            gate=auto          :: product_repo
  [6] Security (stub)          stub/auto-pass     :: security_reqs
  [7] Analytics (stub)         stub/auto-pass     :: analytics_plan
  [8] Ops Readiness (stub)     stub/auto-pass     :: prr
```

### 2 + 3. Vision in → autonomy + HITL gates

The run goes autonomous until it hits a gate, then **pauses for a human**. Here the demo
auto-approves each gate; in real use you approve/reject from the CLI, dashboard, or your IDE
(MCP). `always-human` stages always pause; `auto-if-eval` stages pause only if they miss the
eval bar.

```text
  vision: A platform that helps small teams run governed AI agents safely, with approvals, evals, and a full audit trail.
  -> status=awaiting_approval  stage=intake

  GATE [intake]   mode=always-human eval=1.0 -> APPROVE
  GATE [strategy] mode=always-human eval=1.0 -> APPROVE
  GATE [ux]       mode=always-human eval=1.0 -> APPROVE
  -> final status=completed  cost=$0.0000
```

### 4. Parallelism — agents fan out between gates

The scheduler is topological over the DAG: independent artifacts run **in parallel waves**
under a concurrency limit + budget governor. Discovery fans out 3-wide; UX runs
personas/flows together, then the mockup once they exist.

```text
  discovery    waves=[['business_case', 'competitive_analysis', 'user_research']] maxParallelism=3
  strategy     waves=[['ai_capability_map', 'prd']]                                maxParallelism=2
  ux           waves=[['personas', 'user_flows'], ['mockup']]                      maxParallelism=2
  technical    waves=[['system_architecture'], ['api_spec', 'db_schema']]          maxParallelism=2
```

### 5. Artifacts — every one reviewed (Critic + red-team) and eval-gated

```text
  vision_brief           approved    eval=1.0
  user_research          approved    eval=1.0
  competitive_analysis   approved    eval=1.0
  business_case          approved    eval=1.0
  prd                    approved    eval=1.0
  ai_capability_map      approved    eval=1.0
  personas               approved    eval=1.0
  user_flows             approved    eval=1.0
  mockup                 approved    eval=1.0  -> ux/mockup.html
  system_architecture    approved    eval=1.0
  api_spec               approved    eval=1.0
  db_schema              approved    eval=1.0
  product_repo           approved    eval=1.0  -> scaffold/<slug>
  security_reqs          auto_passed eval=1.0
  analytics_plan         auto_passed eval=1.0
  prr                    auto_passed eval=1.0
```

### 6. Tangible output — on disk

A rendered HTML mockup and a real, runnable scaffolded product repo (10 files):

```text
mockup : <workspace>/runs/<run_id>/artifacts/ux/mockup.html
repo   : <workspace>/runs/<run_id>/artifacts/scaffold/<slug>/

  .gitignore
  pyproject.toml
  README.md
  requirements.txt
  app/__init__.py
  app/main.py
  app/models.py
  evals/run_eval.py
  tests/__init__.py
  tests/test_health.py
```

The mockup is a self-contained dark-theme single page (personas + screen flows + CTA),
openable straight in a browser or previewed at `/runs/{id}/mockup` on the dashboard.

### 7. AI Gateway — egress cost + cache

Every model call goes through one egress with cost/latency tracking and a semantic cache.
Offline it resolves to the deterministic provider — identical output, **$0**.

```text
requests=13 byProvider={'deterministic': 13} cacheHitRate=0.0 costPerRequest=$0.0
```

### 8. Audit — the append-only "why"

Every decision is recorded: who/what/why, per stage and artifact (last events shown).

```text
artifact_produced  system  analytics/analytics_plan  Auto-pass placeholder for Analytics Plan
eval_gate_pass     system  analytics/-               Stub stage auto-passed.
gate_auto_approved system  analytics/-               Auto-approved (eval 1.0 vs bar 0.75).
stage_started      system  ops/-
artifact_produced  system  ops/prr                   Auto-pass placeholder for Production Readiness
eval_gate_pass     system  ops/-                     Stub stage auto-passed.
gate_auto_approved system  ops/-                     Auto-approved (eval 1.0 vs bar 0.75).
run_completed      system  -/-                       Run completed; cost $0.0000, 16 artifacts
```

### Result

```text
PASS — vision in -> approved, eval-passing artifact set + scaffolded repo out, fully audited.
```

---

## What just happened (mapped to the design)

| You saw | The mechanism |
| --- | --- |
| Stages/artifacts/gates as a list | The lifecycle **blueprint** (data) — `src/forge_os/program/lifecycle.blueprint.yaml` |
| Run paused, then resumed on approve | Durable **HITL gates** (interrupt/resume), keyed by `run_id` |
| Discovery ran 3 artifacts at once | Topological **parallel scheduler** + concurrency/budget governor |
| `eval=1.0` on every artifact | **Eval-as-gate**: an artifact must clear its quality bar to pass |
| `auto-if-eval` vs `always-human` | The **materiality dial** per stage |
| `cost=$0.0000`, `deterministic` provider | The **AI Gateway** (routing/cache/fallback/cost), offline mode |
| The "why" trail | Append-only **audit** log |

## Same run, other surfaces

The kernel is a headless engine; these are just clients over the **same durable workspace**
(start in one, approve in another):

- **CLI** — `forge run "vision..."` (start + auto-approve), or `forge start` / `status` /
  `approve` / `reject` / `audit`.
- **API + dashboard** — `uvicorn forge_os.api:app --port 8099`, then open
  <http://localhost:8099/> (start runs, approve/reject gates, preview the mockup).
- **MCP** (Cursor / VS Code / Antigravity / Claude Desktop) — `forge-mcp`; tools
  `forge_start_run`, `forge_status`, `forge_approve`/`reject`, `forge_get_artifact`,
  `forge_list_runs`, `forge_audit`, `forge_blueprint`.

## Going live (no code changes)

Set `FORGE_MODE=live` + a provider key (Gemini free tier recommended) and the same agents
call real models behind the Gateway, validate the structured-output contract, reprompt on
invalid JSON, and **fall back to the seed** if a model never complies — so a run is always
reproducible and never hard-fails. See [`.env.example`](../../.env.example).
