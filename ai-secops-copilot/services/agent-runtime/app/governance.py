"""Confidence-gated governance (two thresholds -> three dispositions).

This is the heart of the "governed automation" story and is intentionally pure
(stdlib only) so it is trivially unit-testable and reusable from the eval
harness. See ADR-005 and PRODUCT_VISION.md "Governance Model".

    confidence >= auto_threshold              -> AUTO_EXECUTE
    suggest_threshold <= confidence < auto    -> HUMAN_APPROVAL
    confidence < suggest_threshold            -> ESCALATE
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Action, Disposition

# Defaults from PRODUCT_VISION.md. Tune from eval data, not by guessing (ADR-005).
DEFAULT_AUTO_THRESHOLD = 0.90
DEFAULT_SUGGEST_THRESHOLD = 0.60


@dataclass(frozen=True)
class GovernanceDecision:
    disposition: Disposition
    requires_human: bool
    reason: str


def evaluate(
    confidence: float,
    recommended_action: Action,
    *,
    auto_threshold: float = DEFAULT_AUTO_THRESHOLD,
    suggest_threshold: float = DEFAULT_SUGGEST_THRESHOLD,
) -> GovernanceDecision:
    """Map a confidence score + recommended action to a governance disposition."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be in [0, 1], got {confidence!r}")
    if suggest_threshold > auto_threshold:
        raise ValueError("suggest_threshold cannot exceed auto_threshold")

    # An explicit escalate recommendation always routes to a human, regardless
    # of confidence (e.g. an ambiguous trust boundary the model flagged).
    if recommended_action is Action.ESCALATE:
        return GovernanceDecision(
            disposition=Disposition.ESCALATE,
            requires_human=True,
            reason="Model recommended escalation (ambiguous/uncertain finding).",
        )

    if confidence >= auto_threshold:
        return GovernanceDecision(
            disposition=Disposition.AUTO_EXECUTE,
            requires_human=False,
            reason=f"Confidence {confidence:.2f} >= auto threshold {auto_threshold:.2f}.",
        )
    if confidence >= suggest_threshold:
        return GovernanceDecision(
            disposition=Disposition.HUMAN_APPROVAL,
            requires_human=True,
            reason=(
                f"Confidence {confidence:.2f} in approval band "
                f"[{suggest_threshold:.2f}, {auto_threshold:.2f})."
            ),
        )
    return GovernanceDecision(
        disposition=Disposition.ESCALATE,
        requires_human=True,
        reason=f"Confidence {confidence:.2f} < suggest threshold {suggest_threshold:.2f}.",
    )
