"""Gate materiality dial + Critic/red-team review scoring."""

from __future__ import annotations

from forge_kernel.agents.reviewer import Reviewer
from forge_kernel.blueprint import ArtifactSpec
from forge_kernel.config import GATE_ALWAYS_HUMAN, GATE_AUTO, GATE_AUTO_IF_EVAL
from forge_kernel.gates import GateOutcome, evaluate_gate
from forge_kernel.state import ArtifactRecord


def test_auto_mode_always_passes():
    d = evaluate_gate(mode=GATE_AUTO, eval_score=0.1, quality_bar=0.9)
    assert d.outcome == GateOutcome.AUTO_APPROVED


def test_auto_if_eval_passes_above_bar_and_escalates_below():
    above = evaluate_gate(mode=GATE_AUTO_IF_EVAL, eval_score=0.9, quality_bar=0.75)
    below = evaluate_gate(mode=GATE_AUTO_IF_EVAL, eval_score=0.5, quality_bar=0.75)
    assert above.outcome == GateOutcome.AUTO_APPROVED
    assert below.outcome == GateOutcome.AWAITING_HUMAN


def test_always_human_pauses_regardless_of_eval():
    d = evaluate_gate(mode=GATE_ALWAYS_HUMAN, eval_score=1.0, quality_bar=0.0)
    assert d.outcome == GateOutcome.AWAITING_HUMAN


def _spec(rubric):
    return ArtifactSpec(key="a", title="A", role="r", stage="s", rubric=tuple(rubric))


def test_reviewer_scores_full_rubric_coverage():
    spec = _spec(["problem", "features", "metrics"])
    rec = ArtifactRecord(key="a", title="A", stage="s", role="r",
                         content={"problem": "p", "features": "f", "metrics": "m"})
    review = Reviewer().review(spec, rec)
    assert review.critic_score == 1.0
    assert review.eval_score == 1.0
    assert review.redteam_findings == []


def test_reviewer_flags_gaps_and_penalizes():
    spec = _spec(["problem", "features", "metrics"])
    rec = ArtifactRecord(key="a", title="A", stage="s", role="r", content={"problem": "p"})
    review = Reviewer().review(spec, rec)
    assert review.critic_score < 1.0
    assert any("metrics" in f for f in review.redteam_findings)
    assert review.eval_score <= review.critic_score
