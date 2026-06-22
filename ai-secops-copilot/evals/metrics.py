"""Metric computation for the evaluation harness (stdlib only).

Reports the Platform KPIs from PRODUCT_VISION.md that are measurable offline:
severity-classification accuracy + confusion matrix, per-class precision/recall/F1
(macro-averaged), ticket-action accuracy, and false-positive detection
precision/recall/F1. No third-party dependencies (no numpy/pandas) so the harness
runs anywhere with a bare Python install.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

SEVERITIES = ["info", "low", "medium", "high", "critical"]


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def accuracy(pairs: Sequence[tuple]) -> float:
    """pairs: iterable of (predicted, expected)."""
    if not pairs:
        return 0.0
    correct = sum(1 for pred, exp in pairs if pred == exp)
    return _safe_div(correct, len(pairs))


def confusion_matrix(pairs: Sequence[tuple], labels: Sequence[str]) -> Dict[str, Dict[str, int]]:
    """Rows = expected (true) label, Cols = predicted label."""
    matrix = {true: {pred: 0 for pred in labels} for true in labels}
    for pred, exp in pairs:
        if exp in matrix and pred in matrix[exp]:
            matrix[exp][pred] += 1
    return matrix


def per_class_prf(pairs: Sequence[tuple], labels: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Precision/recall/F1/support per class for a multi-class problem."""
    report: Dict[str, Dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for pred, exp in pairs if pred == label and exp == label)
        fp = sum(1 for pred, exp in pairs if pred == label and exp != label)
        fn = sum(1 for pred, exp in pairs if pred != label and exp == label)
        support = sum(1 for _, exp in pairs if exp == label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        report[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return report


def macro_f1(per_class: Dict[str, Dict[str, float]]) -> float:
    present = [m["f1"] for m in per_class.values() if m["support"] > 0]
    return _safe_div(sum(present), len(present))


def binary_prf(predicted_positive: Sequence[bool], actual_positive: Sequence[bool]) -> Dict[str, float]:
    """Precision/recall/F1 for a binary detector (e.g. false-positive detection)."""
    tp = sum(1 for p, a in zip(predicted_positive, actual_positive) if p and a)
    fp = sum(1 for p, a in zip(predicted_positive, actual_positive) if p and not a)
    fn = sum(1 for p, a in zip(predicted_positive, actual_positive) if not p and a)
    tn = sum(1 for p, a in zip(predicted_positive, actual_positive) if not p and not a)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def latency_stats(latencies_ms: List[float]) -> Dict[str, float]:
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    ordered = sorted(latencies_ms)
    n = len(ordered)

    def pct(p: float) -> float:
        if n == 1:
            return ordered[0]
        idx = min(n - 1, max(0, round(p * (n - 1))))
        return ordered[idx]

    return {
        "mean_ms": sum(ordered) / n,
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "max_ms": ordered[-1],
    }
