"""Score aggregation + regression gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


def aggregate_eval(scores: Sequence[float]) -> float:
    """Aggregate per-artifact eval scores into one stage score (mean).

    An empty stage (e.g. a stub with no scored artifacts) is treated as a full pass, so
    auto-pass placeholder stages never block a run.
    """
    scores = [s for s in scores if s is not None]
    if not scores:
        return 1.0
    return round(sum(scores) / len(scores), 4)


@dataclass
class RegressionGate:
    """Fail-the-build gate: every metric must meet or exceed its threshold."""

    thresholds: Mapping[str, float]
    failures: list[str] = field(default_factory=list)

    def check(self, metrics: Mapping[str, float]) -> bool:
        self.failures = []
        for key, floor in self.thresholds.items():
            value = metrics.get(key)
            if value is None:
                self.failures.append(f"{key}: missing (threshold {floor})")
            elif value < floor:
                self.failures.append(f"{key}: {value:.4f} < threshold {floor}")
        return not self.failures

    @property
    def passed(self) -> bool:
        return not self.failures
