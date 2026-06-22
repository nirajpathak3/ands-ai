#!/usr/bin/env python3
"""Evaluation harness for AI Security Operations Copilot.

Runs a predictor over the golden findings dataset and reports the offline
Platform KPIs from PRODUCT_VISION.md:

  * Severity-classification accuracy (+ confusion matrix, per-class P/R/F1)
  * Ticket-action accuracy
  * False-positive detection precision / recall / F1
  * Mean processing latency

It also supports a regression *gate* (non-zero exit if metrics fall below
thresholds) so it can run in CI after every change, and a ``--baseline``
comparison to capture before/after deltas (e.g. "this prompt change recovered a
6% severity regression").

Runs with a bare Python install (stdlib only) and the built-in ``heuristic``
predictor, so it is runnable from Day 1 with no API keys or services.

Usage:
    python evals/run_eval.py
    python evals/run_eval.py --predictor heuristic --gate
    python evals/run_eval.py --baseline evals/runs/<previous>.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics  # noqa: E402
import predictors  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "datasets" / "findings" / "security-findings-v1.json"
DEFAULT_OUT_DIR = REPO_ROOT / "evals" / "runs"

# Default regression-gate thresholds. Tuned to sit just under the current
# heuristic baseline so a regression trips the gate; raise these as the
# LLM-backed predictor improves.
DEFAULT_THRESHOLDS = {
    "severity_accuracy": 0.80,
    "action_accuracy": 0.80,
    "fp_detection_f1": 0.0,
}


def _git_commit() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load_dataset(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "findings" not in data or not isinstance(data["findings"], list):
        raise SystemExit(f"Dataset {path} has no 'findings' array.")
    return data


def evaluate(dataset: dict, predictor_name: str) -> dict:
    predictor = predictors.get_predictor(predictor_name)
    findings: List[dict] = dataset["findings"]

    severity_pairs = []  # (predicted, expected)
    action_pairs = []
    predicted_fp: List[bool] = []
    actual_fp: List[bool] = []
    latencies_ms: List[float] = []
    per_finding: List[dict] = []

    for finding in findings:
        label = finding.get("label", {})
        expected_severity = label.get("severity")
        expected_action = label.get("expectedAction")
        is_fp = bool(label.get("isFalsePositive", False))

        start = time.perf_counter()
        prediction = predictor(finding)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)

        pred_severity = prediction.get("severity")
        pred_action = prediction.get("action")
        pred_suppress = pred_action == "suppress"

        severity_pairs.append((pred_severity, expected_severity))
        action_pairs.append((pred_action, expected_action))
        predicted_fp.append(pred_suppress)
        actual_fp.append(is_fp)

        per_finding.append({
            "id": finding.get("id"),
            "cwe": finding.get("cwe"),
            "expectedSeverity": expected_severity,
            "predictedSeverity": pred_severity,
            "severityCorrect": pred_severity == expected_severity,
            "expectedAction": expected_action,
            "predictedAction": pred_action,
            "actionCorrect": pred_action == expected_action,
            "isFalsePositive": is_fp,
            "predictedSuppress": pred_suppress,
            "confidence": prediction.get("confidence"),
        })

    severity_per_class = metrics.per_class_prf(severity_pairs, metrics.SEVERITIES)
    action_per_class = metrics.per_class_prf(action_pairs, predictors.ACTIONS)

    summary = {
        "count": len(findings),
        "severityAccuracy": metrics.accuracy(severity_pairs),
        "severityMacroF1": metrics.macro_f1(severity_per_class),
        "actionAccuracy": metrics.accuracy(action_pairs),
        "fpDetection": metrics.binary_prf(predicted_fp, actual_fp),
        "latency": metrics.latency_stats(latencies_ms),
    }

    return {
        "meta": {
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "predictor": predictor_name,
            "dataset": dataset.get("name"),
            "datasetVersion": dataset.get("version"),
            "gitCommit": _git_commit(),
        },
        "summary": summary,
        "severityConfusionMatrix": metrics.confusion_matrix(severity_pairs, metrics.SEVERITIES),
        "severityPerClass": severity_per_class,
        "actionPerClass": action_per_class,
        "perFinding": per_finding,
    }


def apply_gate(report: dict, thresholds: Dict[str, float]) -> dict:
    summary = report["summary"]
    actuals = {
        "severity_accuracy": summary["severityAccuracy"],
        "action_accuracy": summary["actionAccuracy"],
        "fp_detection_f1": summary["fpDetection"]["f1"],
    }
    failures = []
    for key, minimum in thresholds.items():
        actual = actuals.get(key, 0.0)
        if actual + 1e-9 < minimum:
            failures.append({"metric": key, "actual": actual, "min": minimum})
    return {"enabled": True, "thresholds": thresholds, "passed": not failures, "failures": failures}


def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def print_report(report: dict, baseline: Optional[dict]) -> None:
    meta = report["meta"]
    s = report["summary"]

    print("=" * 70)
    print("  AI Security Operations Copilot - Evaluation Report")
    print("=" * 70)
    print(f"  predictor      : {meta['predictor']}")
    print(f"  dataset        : {meta['dataset']} ({meta['datasetVersion']})  n={s['count']}")
    print(f"  git commit     : {meta.get('gitCommit') or 'n/a'}")
    print(f"  timestamp      : {meta['timestamp']}")
    print("-" * 70)

    def line(label: str, value: float, base_key: Optional[tuple] = None) -> None:
        delta = ""
        if baseline and base_key:
            node = baseline
            for k in base_key:
                node = node.get(k, {}) if isinstance(node, dict) else {}
            if isinstance(node, (int, float)):
                d = value - node
                arrow = "up" if d > 0 else ("down" if d < 0 else "==")
                delta = f"   ({arrow} {d * 100:+.1f} pts vs baseline)"
        print(f"  {label:<28}: {_pct(value)}{delta}")

    line("Severity accuracy", s["severityAccuracy"], ("summary", "severityAccuracy"))
    line("Severity macro-F1", s["severityMacroF1"], ("summary", "severityMacroF1"))
    line("Action accuracy", s["actionAccuracy"], ("summary", "actionAccuracy"))
    fp = s["fpDetection"]
    line("FP detection precision", fp["precision"], ("summary", "fpDetection", "precision"))
    line("FP detection recall", fp["recall"], ("summary", "fpDetection", "recall"))
    line("FP detection F1", fp["f1"], ("summary", "fpDetection", "f1"))
    print(f"  {'FP detection (TP/FP/FN/TN)':<28}: {fp['tp']}/{fp['fp']}/{fp['fn']}/{fp['tn']}")
    lat = s["latency"]
    print(f"  {'Latency mean / p95':<28}: {lat['mean_ms']:.2f} ms / {lat['p95_ms']:.2f} ms")
    print("-" * 70)

    print("  Severity confusion matrix (rows=true, cols=predicted)")
    labels = metrics.SEVERITIES
    header = " " * 12 + "".join(f"{lab[:4]:>8}" for lab in labels)
    print("  " + header)
    cm = report["severityConfusionMatrix"]
    for true_label in labels:
        row = "".join(f"{cm[true_label][pred]:>8}" for pred in labels)
        print(f"  {true_label:>10}  {row}")
    print("-" * 70)

    print("  Severity per-class (precision / recall / F1 / support)")
    for label in labels:
        m = report["severityPerClass"][label]
        print(f"  {label:>10}  P={_pct(m['precision'])}  R={_pct(m['recall'])}  "
              f"F1={_pct(m['f1'])}  n={int(m['support'])}")
    print("-" * 70)

    print("  Action per-class (precision / recall / F1 / support)")
    for label in predictors.ACTIONS:
        m = report["actionPerClass"][label]
        print(f"  {label:>14}  P={_pct(m['precision'])}  R={_pct(m['recall'])}  "
              f"F1={_pct(m['f1'])}  n={int(m['support'])}")

    if report.get("gate", {}).get("enabled"):
        gate = report["gate"]
        print("-" * 70)
        status = "PASS" if gate["passed"] else "FAIL"
        print(f"  Regression gate: {status}")
        for f in gate["failures"]:
            print(f"    - {f['metric']}: {_pct(f['actual'])} < min {_pct(f['min'])}")
    print("=" * 70)


def write_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"eval-{report['meta']['predictor']}-{stamp}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    latest = out_dir / "latest.json"
    with latest.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return out_path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to the golden dataset JSON.")
    parser.add_argument("--predictor", default="heuristic", choices=predictors.available_predictors(),
                        help="Predictor to evaluate (default: heuristic).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Directory for run reports.")
    parser.add_argument("--no-write", action="store_true", help="Do not persist a report file.")
    parser.add_argument("--gate", action="store_true", help="Enable the regression gate (non-zero exit on failure).")
    parser.add_argument("--min-severity-accuracy", type=float, default=DEFAULT_THRESHOLDS["severity_accuracy"])
    parser.add_argument("--min-action-accuracy", type=float, default=DEFAULT_THRESHOLDS["action_accuracy"])
    parser.add_argument("--min-fp-f1", type=float, default=DEFAULT_THRESHOLDS["fp_detection_f1"])
    parser.add_argument("--baseline", type=Path, default=None, help="Prior report JSON to compute deltas against.")
    parser.add_argument("--quiet", action="store_true", help="Suppress the console report (still writes JSON).")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    dataset = load_dataset(args.dataset)
    report = evaluate(dataset, args.predictor)

    if args.gate:
        report["gate"] = apply_gate(report, {
            "severity_accuracy": args.min_severity_accuracy,
            "action_accuracy": args.min_action_accuracy,
            "fp_detection_f1": args.min_fp_f1,
        })

    baseline = None
    if args.baseline:
        if args.baseline.exists():
            with args.baseline.open("r", encoding="utf-8") as fh:
                baseline = json.load(fh)
        else:
            print(f"[warn] baseline not found: {args.baseline}", file=sys.stderr)

    if not args.quiet:
        print_report(report, baseline)

    if not args.no_write:
        out_path = write_report(report, args.out)
        if not args.quiet:
            print(f"  report written: {out_path.relative_to(REPO_ROOT)}")

    if args.gate and not report["gate"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
