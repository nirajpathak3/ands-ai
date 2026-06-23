"""LLM-as-judge evaluation harness (DeepEval-style), offline by default.

Judging *answer quality* (is the reasoning consistent, calibrated, and grounded?)
needs a model. To keep the harness runnable with no API keys and reproducible in CI,
the default ``DeterministicJudge`` applies a transparent rubric instead of a model;
a ``GatewayJudge`` (Day 11) swaps a real LLM judge in behind the same ``Judge`` seam
— exactly the pattern used by the runtime's ``LLMClient``.

The rubric scores attributes a *misbehaving* analyzer would violate, so it is a real
regression signal rather than a tautology:

  * reason_present       - a non-trivial explanation exists
  * action_consistent    - recommendedAction agrees with severity
  * confidence_calibrated- confidence sits in a sane band for the action
  * grounded             - the reason references the finding's weakness/decision

Each item scores in [0, 1] (mean of the boolean checks); the suite reports the mean
overall score and per-check pass rates.
"""

from __future__ import annotations

from typing import Callable, Dict, Protocol

Finding = Dict[str, object]
Prediction = Dict[str, object]

# Reasoning vocabulary a grounded explanation tends to use, by action.
_GROUNDING_TERMS = (
    "injection", "untrusted", "user", "input", "sink", "false positive", "escalat",
    "human", "ambiguous", "trust boundary", "ticket", "remediat", "vulnerab",
    "deserializ", "hash", "template", "secret", "placeholder", "non-production",
    "test", "safe", "cwe",
)


class Judge(Protocol):
    name: str

    def score(self, finding: Finding, prediction: Prediction) -> dict:
        ...


class DeterministicJudge:
    """Offline, rubric-based judge (the no-API-keys default)."""

    name = "deterministic"

    def score(self, finding: Finding, prediction: Prediction) -> dict:
        severity = str(prediction.get("severity", "")).lower()
        action = str(prediction.get("action", "")).lower()
        confidence = float(prediction.get("confidence", 0.0) or 0.0)
        reason = str(prediction.get("reason", "") or "")
        reason_l = reason.lower()

        checks: dict[str, bool] = {}
        checks["reason_present"] = len(reason.strip()) >= 20

        if action == "suppress":
            checks["action_consistent"] = severity in {"info", "low"}
            checks["confidence_calibrated"] = confidence >= 0.7
        elif action == "create_ticket":
            checks["action_consistent"] = severity not in {"info", ""}
            checks["confidence_calibrated"] = confidence >= 0.6
        elif action == "escalate":
            # Escalation is the "uncertain" path: confidence should not be high.
            checks["action_consistent"] = True
            checks["confidence_calibrated"] = confidence <= 0.8
        else:
            checks["action_consistent"] = False
            checks["confidence_calibrated"] = False

        checks["grounded"] = any(term in reason_l for term in _GROUNDING_TERMS)

        passed = sum(1 for ok in checks.values() if ok)
        overall = passed / len(checks)
        return {"overall": overall, "checks": checks}


class GatewayJudge:
    """Real LLM judge via the AI Gateway. Wired on Day 11 (stub for now)."""

    name = "gateway"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def score(self, finding: Finding, prediction: Prediction) -> dict:
        raise NotImplementedError(
            "GatewayJudge is wired on Day 11; until then the harness uses "
            "DeterministicJudge (offline rubric)."
        )


_JUDGES: Dict[str, Callable[[], Judge]] = {
    "deterministic": DeterministicJudge,
}


def get_judge(name: str = "deterministic") -> Judge:
    try:
        return _JUDGES[name]()
    except KeyError:
        valid = ", ".join(sorted(_JUDGES))
        raise SystemExit(f"Unknown judge '{name}'. Available: {valid}")


def evaluate_judge(findings: list, predictor: Callable[[Finding], Prediction], judge: Judge) -> dict:
    """Run the judge over every finding's prediction and aggregate the scores."""
    check_totals: dict[str, int] = {}
    overall_sum = 0.0
    n = 0
    worst: list[dict] = []

    for finding in findings:
        prediction = predictor(finding)
        result = judge.score(finding, prediction)
        overall_sum += float(result["overall"])
        n += 1
        for name, ok in result["checks"].items():
            check_totals[name] = check_totals.get(name, 0) + (1 if ok else 0)
        if result["overall"] < 1.0:
            worst.append({
                "id": finding.get("id"),
                "action": prediction.get("action"),
                "severity": prediction.get("severity"),
                "overall": round(float(result["overall"]), 3),
                "failed": [k for k, ok in result["checks"].items() if not ok],
            })

    denom = n or 1
    return {
        "judge": judge.name,
        "count": n,
        "overall": overall_sum / denom,
        "checkPassRates": {k: v / denom for k, v in check_totals.items()},
        "belowPerfect": worst,
    }
