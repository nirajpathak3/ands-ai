# Evaluation Harness

Offline evaluation for the AI Security Operations Copilot. Measures the
Platform KPIs from [`docs/PRODUCT_VISION.md`](../docs/PRODUCT_VISION.md) against
the golden dataset and gates regressions.

> **Runs with a bare Python install — no third-party packages, no API keys, no
> services.** This is the Day-1 safety net so we can "measure after every change"
> from the very start.

## Quickstart

```bash
# From the repo root:
python evals/run_eval.py
```

Add the regression gate (non-zero exit if metrics drop below thresholds — use in CI):

```bash
python evals/run_eval.py --gate
```

Compare against a previous run to capture a before/after delta:

```bash
python evals/run_eval.py --baseline evals/runs/latest.json
```

## What it reports

- **Severity-classification accuracy** + confusion matrix + per-class precision/recall/F1
- **Ticket-action accuracy** (`create_ticket` / `suppress` / `escalate`)
- **False-positive detection** precision / recall / F1
- **Mean / p95 processing latency**

## Predictors

A *predictor* maps a finding to `{severity, action, confidence, reason}`.

| Name        | Status        | Description                                                        |
| ----------- | ------------- | ----------------------------------------------------------------- |
| `heuristic` | **available** | Dependency-free CWE→severity baseline + weak path-based FP guess. |
| `runtime`   | planned       | LangGraph/LLM predictor via `services/agent-runtime` (Day 2+).    |

```bash
python evals/run_eval.py --predictor heuristic
```

## Baseline (heuristic, security-findings-v1, n=50)

| Metric                 | Value  |
| ---------------------- | ------ |
| Severity accuracy      | 86.0%  |
| Action accuracy        | 84.0%  |
| FP detection precision | 100.0% |
| FP detection recall    | 37.5%  |

The heuristic is strong on severity (CWE mapping) but **cannot detect most false
positives and never escalates** — exactly the gap the LLM + RAG predictor is
meant to close. That before/after delta is the headline evaluation story.

## Files

- `run_eval.py` — CLI entry point (load → predict → score → report → gate).
- `metrics.py` — accuracy, confusion matrix, per-class P/R/F1, binary P/R/F1, latency.
- `predictors.py` — predictor implementations + registry.
- `runs/` — generated reports (git-ignored); `runs/latest.json` is the most recent.
