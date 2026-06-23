"""Governance evaluation: autonomy vs. safety, and threshold tuning (ADR-005).

Turns the governance gate into a *measured* policy instead of guessed thresholds.
For a given predictor + policy it reports:

  * automationRate / reviewRate / escalationRate - where decisions land
  * autoActionAccuracy - of the decisions taken WITHOUT a human, how many match the
    expected action. This is the safety metric: "when we act alone, are we right?"
  * missedAutomations  - correct predictions we still sent to a human (efficiency cost)

It also sweeps the auto-threshold to expose the autonomy/safety trade-off, which is how
the operating point is chosen from data rather than guessed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AGENT_RUNTIME = _REPO_ROOT / "services" / "agent-runtime"
if str(_AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_AGENT_RUNTIME))


def evaluate_governance(
    findings: list, predictor: Callable[[dict], dict], policy=None
) -> Optional[dict]:
    """Apply the governance policy to each prediction and measure autonomy vs safety."""
    try:
        from app.domain import Action
        from app.governance import GovernancePolicy, evaluate
    except Exception as exc:  # noqa: BLE001 - harness degrades gracefully
        return {"available": False, "reason": f"governance not importable: {exc}"}

    policy = policy or GovernancePolicy()
    counts = {"auto_execute": 0, "human_approval": 0, "escalate": 0}
    auto_total = 0
    auto_correct = 0
    missed = 0

    for finding in findings:
        pred = predictor(finding)
        action = str(pred["action"])
        confidence = float(pred["confidence"])
        decision = evaluate(confidence, Action(action), policy=policy)
        disposition = decision.disposition.value
        counts[disposition] = counts.get(disposition, 0) + 1

        expected = (finding.get("label", {}) or {}).get("expectedAction")
        is_correct = action == expected
        if disposition == "auto_execute":
            auto_total += 1
            if is_correct:
                auto_correct += 1
        elif is_correct:
            missed += 1

    n = len(findings) or 1
    return {
        "available": True,
        "policy": {
            "autoThreshold": policy.auto_threshold,
            "suggestThreshold": policy.suggest_threshold,
            "suppressAutoThreshold": policy.suppress_auto_threshold,
        },
        "count": len(findings),
        "dispositionCounts": counts,
        "automationRate": counts["auto_execute"] / n,
        "reviewRate": counts["human_approval"] / n,
        "escalationRate": counts["escalate"] / n,
        "autoExecuted": auto_total,
        "autoActionAccuracy": (auto_correct / auto_total) if auto_total else 1.0,
        "missedAutomations": missed,
    }


def sweep_auto_threshold(
    findings: list,
    predictor: Callable[[dict], dict],
    thresholds: list[float],
    *,
    suggest: float = 0.60,
    suppress: float = 0.95,
) -> list[dict]:
    """Sweep the auto-threshold to show the autonomy/safety trade-off."""
    try:
        from app.governance import GovernancePolicy
    except Exception:  # noqa: BLE001
        return []

    rows: list[dict] = []
    for t in thresholds:
        policy = GovernancePolicy(
            auto_threshold=t,
            suggest_threshold=min(suggest, t),
            suppress_auto_threshold=max(suppress, t),
        )
        m = evaluate_governance(findings, predictor, policy)
        if m and m.get("available"):
            rows.append({
                "autoThreshold": t,
                "automationRate": m["automationRate"],
                "autoActionAccuracy": m["autoActionAccuracy"],
                "missedAutomations": m["missedAutomations"],
            })
    return rows
