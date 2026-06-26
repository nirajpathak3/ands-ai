# ANDS Forge OS

> An autonomous, multi-agent **product-development operating system**. Give it a product
> vision the way you'd brief a CTO/CPO; it runs the product-development lifecycle —
> Discovery → Strategy → UX → Architecture → … — coordinating specialized agents that work
> in **parallel**, pausing only for **human approval at each gate**, and emitting real,
> reviewable artifacts with a full **cost + audit trail** of every decision.

This repo runs an end-to-end vertical slice **fully offline and deterministic** (no API
keys, $0) by default. One unified, skill-pack-driven agent backs every role: offline it
echoes a reproducible **seed** through the AI Gateway; with `FORGE_MODE=live` the *same*
agent calls real providers, validates a **structured-output contract**, **reprompts** on
invalid JSON, and **falls back to the seed** if a model never complies — so a run is always
reproducible and never hard-fails.

```
vision  ──▶  HITL plan approval  ──▶  Discovery (∥)  ──▶  PRD  ──▶  UX (personas + flows
        + one rendered HTML mockup)  ──▶  System architecture + API/DB sketch  ──▶  a real
        scaffolded product repo on disk
```

Every stage has a HITL gate (materiality dial), every artifact is reviewed by a **Critic +
red-team**, at least one stage **fans out in parallel**, and the whole run is gated by
**eval-as-gate** and recorded in an append-only audit trail.

---

## Two layers (kept clean)

The design separates a generic engine from the product it happens to be building, so the
**same kernel runs any project** by loading different data.

| Layer | What it is | Where |
| --- | --- | --- |
| **Forge kernel** | Generic, domain-agnostic engine: supervisor + parallel scheduler (topological over a DAG, with a cost/time **budget governor**) + skill-pack loader + durable **HITL** gates + **eval-as-gate** + **AI gateway** + append-only **audit** + **blackboard** state. Knows nothing about product development. | [`src/forge_kernel/`](src/forge_kernel/) |
| **ANDS Forge OS** | The product-development **program**: the lifecycle **blueprint** + agent **roster** + **skill packs**, loaded as **data**, plus the skill-pack-driven `LLMArtifactAgent` and the FastAPI/CLI edges. | [`src/forge_os/`](src/forge_os/) |

Genericity is preserved because the program (blueprint) and skill packs are **swappable
data** — none of the product-development specifics are hardcoded in the kernel.

Substrate reused/ported from `ai-secops-copilot`: the AI Gateway (routing/fallback/cache/
cost), governance→gate patterns, durable HITL (pause/resume), the eval harness + regression
gate, the in-process tracer, and the persistence/offline-determinism conventions.

---

## Quickstart (offline, no keys)

```bash
pip install -e ".[dev]"          # kernel itself needs zero third-party packages

# 1) Narrated end-to-end demo (vision in -> scaffolded repo out), no server:
python scripts/demo_walkthrough.py        # recorded run: docs/demo/walkthrough.md

# 1b) See the LIVE path with NO API keys (scripted provider: real-looking model
#     output, structured-output validation, bounded reprompt, simulated cost):
python scripts/demo_live_fake.py

# 2) Drive it from the CLI (start + auto-approve every gate):
forge run "A FinOps copilot that detects cloud cost anomalies and proposes safe fixes"

# 3) Or run the API + dashboard:
uvicorn forge_os.api:app --reload --port 8099
#   open http://localhost:8099/   (start a run, approve gates, preview the mockup)
```

The kernel runs **without any third-party package installed**; FastAPI/uvicorn/pyyaml are
only needed for loading the YAML program and serving the edges (`pip install -e ".[dev]"`
covers everything).

---

## The lifecycle program (data)

The lifecycle is declared in [`src/forge_os/program/lifecycle.blueprint.yaml`](src/forge_os/program/lifecycle.blueprint.yaml)
as a DAG of stages → artifacts → owning role → quality bar → gate **materiality**:

- **always-human** — always pause for a human (here: plan, PRD, mockup).
- **auto-if-eval** — auto-pass *iff* the eval bar is met, else escalate to a human.
- **auto** — pass autonomously.

`Security`, `Analytics`, and `Ops` are **auto-pass stubs** for the slice. Swap the
blueprint + skill packs to point the same kernel at a different kind of project.

---

## CLI

```bash
forge start "vision..."            # start; pauses at the first HITL gate
forge status <run_id>              # status + pending gate
forge approve <run_id>             # approve the pending gate and resume
forge reject  <run_id> --feedback "tighten the metrics"   # reopen the stage (bounded)
forge audit   <run_id>             # the append-only "why" trail
forge run "vision..."              # start + auto-approve all gates (demo/CI)
```

Runs are **durable**: a run started on the CLI can be approved from the dashboard and
resumed across sessions/process restarts (keyed by `run_id`), because the blackboard +
audit trail are persisted to the workspace (`FORGE_WORKSPACE`, default `var/`).

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Run dashboard (start runs, approve/reject gates, preview mockup) |
| GET | `/health` | Liveness + config snapshot |
| GET | `/blueprint` | The compiled lifecycle program |
| POST | `/runs` | Start a run `{ "vision": "..." }` |
| GET | `/runs` · `/runs/{id}` | List / fetch run state |
| POST | `/runs/{id}/approve` · `/reject` | Resolve the pending HITL gate |
| GET | `/runs/{id}/artifacts/{key}` | One artifact's content + scores |
| GET | `/runs/{id}/mockup` | The rendered HTML mockup |
| GET | `/runs/{id}/audit` | Append-only audit trail |
| GET | `/gateway/metrics` · `/observability/traces` | Cost/cache + spans |

## MCP (drive Forge from Cursor / VS Code / Antigravity / Claude Desktop)

The kernel is a **headless engine**; environments are just clients. The MCP server exposes
the run lifecycle as agent-callable tools over stdio, sharing the **same durable workspace**
as the CLI and dashboard — so a run started from your IDE can be approved from the dashboard
and vice versa (keyed by `run_id`).

```bash
pip install -e ".[mcp,llm]"
forge-mcp                                  # stdio transport (what MCP clients launch)
```

Register it in an MCP client (e.g. `~/.cursor/mcp.json` or a Claude Desktop config):

```json
{ "mcpServers": { "ands-forge-os": { "command": "forge-mcp" } } }
```

| Tool | Purpose |
| --- | --- |
| `forge_start_run(vision)` | Start a run; pauses at the first HITL gate |
| `forge_status(run_id)` | Stage, cost, artifact statuses, pending gate |
| `forge_approve(run_id, feedback?)` · `forge_reject(run_id, feedback?)` | Resolve the pending gate |
| `forge_get_artifact(run_id, key)` | One artifact's content + scores + path |
| `forge_list_runs()` · `forge_audit(run_id)` · `forge_blueprint()` | Observability |

The tool *logic* lives in [`src/forge_os/mcp_tools.py`](src/forge_os/mcp_tools.py) (dependency-free,
offline-testable); [`mcp_server.py`](src/forge_os/mcp_server.py) is a thin FastMCP wrapper.

---

## Tests, eval gate, CI

```bash
pytest -q                              # unit + end-to-end (offline, deterministic)
python evals/run_eval.py --gate        # regression gate over golden visions (CI gate)
ruff check src tests evals scripts
make check                             # all of the above
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint + tests + the eval
gate on Python 3.11/3.12, then builds the Docker image and smoke-tests the offline demo
inside it.

## Docker

```bash
docker compose up -d --build           # API + dashboard on :8099 (offline)
```

---

## Going live (later build steps)

Everything is offline-deterministic by default. Real providers/behaviors light up **by
configuration only** (see [`.env.example`](.env.example)):

- `FORGE_MODE=live` + a provider key → the skill-pack agents call real models behind the
  AI Gateway, validate structured output, and reprompt on invalid JSON; the Critic/Red-team
  upgrades to **LLM-as-judge** (blended with the heuristic). The deterministic provider +
  seed fallback stay the final safety net, so it never hard-fails. (Offline stays $0 and
  deterministic even if keys are present — real providers are only added in live mode.)
- **Recommended backend: Gemini (free tier).** `GEMINI_API_KEY` from
  [Google AI Studio](https://aistudio.google.com/apikey) — cloud, no PC always-on, no extra
  subscription. `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` also supported.
- **Model tiers — assign which model does which stage** (swap as new models ship, no code):
  `FORGE_MODEL_STRONG` (reasoning: the judge + `FORGE_STRONG_STAGES`) and `FORGE_MODEL_CHEAP`
  (high-volume drafting). A blueprint stage/artifact `model:` pins a specific model.
- `FORGE_ANALYSIS_MAX_RETRIES` → bounded reprompts on invalid structured output (ADR-010).
- No keys but want to *see* the live path: `scripts/demo_live_fake.py` (scripted provider).
- The compiled-graph runner (LangGraph `interrupt`/checkpoint) is a drop-in seam alongside
  the durable inline `RunStore` used by the skeleton.

## Repository layout

```
src/forge_kernel/   blueprint · state · skillpack · scheduler · supervisor · gates ·
                    runner(+RunStore) · gateway/ · tools/ · eval/ · observability/ · audit
src/forge_os/       program/ (blueprint + roster) · skillpacks/ · agents/ (LLMArtifactAgent) · prompts · structured · judge · api · cli · mcp_tools · mcp_server
evals/              golden visions + regression-gate harness
tests/              unit + end-to-end (offline, deterministic)
scripts/            demo_walkthrough.py (narrated, one command)
```

See [`PRODUCT-VISION.md`](../agentic-portfolio/forge/PRODUCT-VISION.md) for the full vision,
the 5-year lifecycle, and the build sequence this repo is executing.
