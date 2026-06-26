"""Gate logic: eval-as-gate + the materiality dial (PRODUCT_VISION §6).

A stage gate combines two signals:

1. **Eval-as-gate** — the aggregate Critic/red-team score for the stage's artifacts vs a
   quality bar. This is the machine-checkable Definition-of-Done.
2. **Materiality dial** — a per-gate mode that decides *who* approves:
   * ``auto``          — pass autonomously (low-stakes stage).
   * ``auto-if-eval``  — pass autonomously **iff** the eval bar is met, else ask a human.
   * ``always-human``  — always pause for a human, regardless of eval.

This is what lets a run feel autonomous without losing control: low-risk stages flow,
high-stakes ones force a human. Pure functions over plain values, so it is trivially
unit-testable and reusable from the eval harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .config import GATE_ALWAYS_HUMAN, GATE_AUTO, GATE_AUTO_IF_EVAL


class GateOutcome(StrEnum):
    AUTO_APPROVED = "auto_approved"
    AWAITING_HUMAN = "awaiting_human"


@dataclass(frozen=True)
class GateDecision:
    outcome: GateOutcome
    passed_eval: bool
    eval_score: float
    quality_bar: float
    mode: str
    reason: str


def evaluate_gate(
    *, mode: str, eval_score: float, quality_bar: float
) -> GateDecision:
    """Decide whether a stage gate auto-passes or must pause for a human."""
    passed_eval = eval_score >= quality_bar

    if mode == GATE_AUTO:
        return GateDecision(
            outcome=GateOutcome.AUTO_APPROVED,
            passed_eval=passed_eval,
            eval_score=eval_score,
            quality_bar=quality_bar,
            mode=mode,
            reason=f"mode=auto: passed autonomously (eval {eval_score:.2f}).",
        )

    if mode == GATE_AUTO_IF_EVAL:
        if passed_eval:
            return GateDecision(
                outcome=GateOutcome.AUTO_APPROVED,
                passed_eval=True,
                eval_score=eval_score,
                quality_bar=quality_bar,
                mode=mode,
                reason=(
                    f"mode=auto-if-eval: eval {eval_score:.2f} >= bar {quality_bar:.2f}; "
                    "auto-approved."
                ),
            )
        return GateDecision(
            outcome=GateOutcome.AWAITING_HUMAN,
            passed_eval=False,
            eval_score=eval_score,
            quality_bar=quality_bar,
            mode=mode,
            reason=(
                f"mode=auto-if-eval: eval {eval_score:.2f} < bar {quality_bar:.2f}; "
                "escalating to human."
            ),
        )

    # always-human (and any unrecognized mode -> safest behavior: ask a human).
    return GateDecision(
        outcome=GateOutcome.AWAITING_HUMAN,
        passed_eval=passed_eval,
        eval_score=eval_score,
        quality_bar=quality_bar,
        mode=GATE_ALWAYS_HUMAN if mode == GATE_ALWAYS_HUMAN else mode,
        reason="mode=always-human: human approval required regardless of eval.",
    )
