#!/usr/bin/env python3
"""Evaluation harness + regression gate for ANDS Forge OS.

Runs each golden vision end-to-end through the offline kernel (auto-approving HITL gates)
and scores the run-level KPIs from PRODUCT_VISION §14:

  * completion_rate        — fraction of visions that reach COMPLETED
  * mean_stage_eval        — mean per-stage eval-as-gate score
  * artifact_coverage      — fraction of expected artifacts produced
  * mockup_render_rate     — fraction of runs that rendered the HTML mockup
  * scaffold_rate          — fraction of runs that scaffolded a repo on disk
  * auto_action_accuracy   — autonomous (auto) gates that should not have needed a human

A regression gate (``--gate``) exits non-zero when any metric falls below its threshold,
so this runs in CI after every change. Fully offline + deterministic (no keys, $0).

Usage:
    python evals/run_eval.py
    python evals/run_eval.py --gate
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from forge_kernel.config import Settings  # noqa: E402
from forge_kernel.eval import RegressionGate  # noqa: E402
from forge_kernel.runner import RunStore  # noqa: E402
from forge_kernel.state import RunStatus  # noqa: E402
from forge_os import build_forge  # noqa: E402

DEFAULT_DATASET = _REPO / "evals" / "datasets" / "visions-v1.json"

DEFAULT_THRESHOLDS = {
    "completion_rate": 1.0,
    "mean_stage_eval": 0.75,
    "artifact_coverage": 1.0,
    "mockup_render_rate": 1.0,
    "scaffold_rate": 1.0,
    "auto_action_accuracy": 1.0,
}


def _run_one(case: dict, workspace: Path) -> dict:
    settings = Settings(workspace=str(workspace))
    forge = build_forge(settings, store=RunStore(workspace))
    run = forge.start(case["vision"])
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 20:
        guard += 1
        run = forge.resume(run.run_id, approved=True, feedback="auto-approved (eval)")

    art_dir = Path(run.workspace_dir)
    produced = set(run.artifacts)
    expected = set(case.get("expect_artifacts", []))
    coverage = len(expected & produced) / len(expected) if expected else 1.0

    files_ok = all((art_dir / f).exists() for f in case.get("expect_files", []))
    scaffold_ok = bool(list((art_dir / "scaffold").glob("*/README.md")))

    stage_evals = [g.eval_score for g in run.gates if g.eval_score is not None]
    # Any auto-approved gate must have actually cleared its eval bar (else we acted blind).
    auto_ok = all(
        g.passed_eval for g in run.gates
        if g.decision == "auto_approved" and g.eval_score is not None and not _is_stub(g)
    )
    return {
        "id": case["id"],
        "status": str(run.status),
        "completed": run.status == RunStatus.COMPLETED,
        "coverage": round(coverage, 4),
        "meanStageEval": round(sum(stage_evals) / len(stage_evals), 4) if stage_evals else 0.0,
        "mockup": files_ok,
        "scaffold": scaffold_ok,
        "autoOk": auto_ok,
        "costUsd": run.cost_usd,
    }


def _is_stub(gate) -> bool:
    return gate.eval_score == 1.0 and gate.stage in ("security", "analytics", "ops")


def evaluate(dataset: dict) -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="forge-eval-") as base:
        for i, case in enumerate(dataset["visions"]):
            rows.append(_run_one(case, Path(base) / f"case-{i}"))

    n = len(rows) or 1
    metrics = {
        "completion_rate": round(sum(r["completed"] for r in rows) / n, 4),
        "mean_stage_eval": round(sum(r["meanStageEval"] for r in rows) / n, 4),
        "artifact_coverage": round(sum(r["coverage"] for r in rows) / n, 4),
        "mockup_render_rate": round(sum(r["mockup"] for r in rows) / n, 4),
        "scaffold_rate": round(sum(r["scaffold"] for r in rows) / n, 4),
        "auto_action_accuracy": round(sum(r["autoOk"] for r in rows) / n, 4),
        "cases": n,
    }
    return metrics, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANDS Forge OS eval harness")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--gate", action="store_true", help="fail (exit 1) on regression")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    metrics, rows = evaluate(dataset)

    if args.json:
        print(json.dumps({"metrics": metrics, "rows": rows}, indent=2))
    else:
        print(f"Eval over {metrics['cases']} golden visions:")
        for k, v in metrics.items():
            if k != "cases":
                print(f"  {k:22s} {v}")
        for r in rows:
            print(f"  - {r['id']:18s} {r['status']:11s} coverage={r['coverage']} "
                  f"mockup={r['mockup']} scaffold={r['scaffold']} eval={r['meanStageEval']}")

    if args.gate:
        gate = RegressionGate(DEFAULT_THRESHOLDS)
        if gate.check(metrics):
            print("\nGATE: PASS — all metrics meet thresholds.")
            return 0
        print("\nGATE: FAIL")
        for f in gate.failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
