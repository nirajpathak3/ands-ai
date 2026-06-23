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

Run the full suite — classification **+ RAG retrieval quality + LLM-as-judge** — and gate it (this is what CI runs):

```bash
python evals/run_eval.py --predictor runtime --all --gate
```

Compare against a previous run to capture a before/after delta:

```bash
python evals/run_eval.py --baseline evals/runs/latest.json
```

## What it reports

- **Severity-classification accuracy** + confusion matrix + per-class precision/recall/F1
- **Ticket-action accuracy** (`create_ticket` / `suppress` / `escalate`)
- **False-positive detection** precision / recall / F1
- **RAG retrieval quality** (`--rag`): KB coverage, hit@1, hit@k, MRR + the list of
  CWEs missing from the corpus (RAGAS-style context relevance, measured on the real retriever)
- **LLM-as-judge** (`--judge`): a reasoning-quality score (reason present, action↔severity
  consistency, confidence calibration, groundedness) via a swappable `Judge` seam
- **Mean / p95 processing latency**

## Predictors

A *predictor* maps a finding to `{severity, action, confidence, reason}`.

| Name        | Status        | Description                                                        |
| ----------- | ------------- | ----------------------------------------------------------------- |
| `heuristic` | **available** | Dependency-free CWE→severity baseline + weak path-based FP guess. |
| `runtime`   | **available** | The agent-runtime analysis core (offline LLM stand-in, Day 2+).   |

```bash
python evals/run_eval.py --predictor heuristic
```

## Judges (LLM-as-judge)

A *judge* scores reasoning quality. The default runs offline; a real LLM judge slots
in behind the same seam on Day 11 (mirrors the runtime's `LLMClient`).

| Name            | Status        | Description                                              |
| --------------- | ------------- | ------------------------------------------------------- |
| `deterministic` | **available** | Transparent rubric, no API keys; reproducible in CI.    |
| `gateway`       | planned       | Real LLM judge via the AI Gateway (Day 11).             |

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

## Runtime vs heuristic (security-findings-v1, n=50)

| Metric             | Heuristic | Runtime |
| ------------------ | --------- | ------- |
| Severity accuracy  | 86.0%     | 96.0%   |
| Action accuracy    | 84.0%     | 100.0%  |
| FP detection F1    | 54.5%     | 100.0%  |
| Retrieval hit@k    | n/a       | 100.0% (KB coverage 56.0%) |
| Judge overall      | n/a       | 100.0%  |

> Honest caveat: the runtime analyzer was calibrated on this same set, so these are a
> strong-rules baseline, not held-out generalization. The eval harness + gate exist to
> make the Day-11 LLM comparison on unseen findings trustworthy.

## Files

- `run_eval.py` — CLI entry point (load → predict → score → report → gate).
- `metrics.py` — accuracy, confusion matrix, per-class P/R/F1, binary P/R/F1, latency.
- `predictors.py` — predictor implementations + registry.
- `retrieval_eval.py` — RAG retrieval-quality metrics over the real retriever.
- `judge.py` — LLM-as-judge seam (deterministic offline judge + Gateway stub).
- `test_eval_harness.py` — harness self-tests (`python -m pytest evals`).
- `runs/` — generated reports (git-ignored); `runs/latest.json` is the most recent.
