"""Confidence-gated governance: a small, auditable policy engine (ADR-005).

Two thresholds -> three dispositions, with an **asymmetric-risk** refinement that is
the heart of the "governed automation" story:

    create_ticket : confidence >= auto_threshold          -> AUTO_EXECUTE
    suppress      : confidence >= suppress_auto_threshold  -> AUTO_EXECUTE  (stricter)
    any action    : suggest_threshold <= confidence < auto -> HUMAN_APPROVAL
                  : confidence < suggest_threshold          -> ESCALATE
    explicit escalate (model)                              -> ESCALATE

Why a *higher* bar to auto-suppress than to auto-ticket: auto-creating a ticket is a
recoverable, low-harm action (a human can close it), but auto-dismissing a finding can
silently hide a real vulnerability — the costlier error. So suppression must clear a
higher confidence bar before it runs without a human. Every decision carries a
machine-readable ``reason_code`` for the audit trail.

Pure stdlib so it stays trivially unit-testable and reusable from the eval harness.
Thresholds are tuned from eval data (see ``evals/governance_eval.py``), not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .domain import Action, Disposition

# Defaults from PRODUCT_VISION.md. Tune from eval data, not by guessing (ADR-005).
DEFAULT_AUTO_THRESHOLD = 0.90
DEFAULT_SUGGEST_THRESHOLD = 0.60
# Stricter bar to auto-suppress (dismissing a real finding is the costlier error).
DEFAULT_SUPPRESS_AUTO_THRESHOLD = 0.95


class ReasonCode(StrEnum):
    """Machine-readable rationale for a governance disposition (audit trail)."""

    MODEL_ESCALATION = "model_escalation"
    AUTO_HIGH_CONFIDENCE = "auto_high_confidence"
    AUTO_SUPPRESS_HIGH_CONFIDENCE = "auto_suppress_high_confidence"
    APPROVAL_BAND = "approval_band"
    SUPPRESS_NEEDS_REVIEW = "suppress_needs_review"
    BELOW_SUGGEST_THRESHOLD = "below_suggest_threshold"


@dataclass(frozen=True)
class GovernancePolicy:
    """The tunable autonomy policy (thresholds + asymmetric suppression bar)."""

    auto_threshold: float = DEFAULT_AUTO_THRESHOLD
    suggest_threshold: float = DEFAULT_SUGGEST_THRESHOLD
    suppress_auto_threshold: float = DEFAULT_SUPPRESS_AUTO_THRESHOLD

    def __post_init__(self) -> None:
        for name in ("auto_threshold", "suggest_threshold", "suppress_auto_threshold"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value!r}")
        if self.suggest_threshold > self.auto_threshold:
            raise ValueError("suggest_threshold cannot exceed auto_threshold")


@dataclass(frozen=True)
class GovernanceDecision:
    disposition: Disposition
    requires_human: bool
    reason: str
    reason_code: ReasonCode


def evaluate(
    confidence: float,
    recommended_action: Action,
    *,
    auto_threshold: float = DEFAULT_AUTO_THRESHOLD,
    suggest_threshold: float = DEFAULT_SUGGEST_THRESHOLD,
    suppress_auto_threshold: float = DEFAULT_SUPPRESS_AUTO_THRESHOLD,
    policy: GovernancePolicy | None = None,
) -> GovernanceDecision:
    """Map a confidence score + recommended action to a governance disposition.

    Pass a ``policy`` to use a bundled threshold set, or the individual ``*_threshold``
    keyword arguments (kept for backwards compatibility and ad-hoc previews).
    """
    if policy is not None:
        auto_threshold = policy.auto_threshold
        suggest_threshold = policy.suggest_threshold
        suppress_auto_threshold = policy.suppress_auto_threshold

    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be in [0, 1], got {confidence!r}")
    if suggest_threshold > auto_threshold:
        raise ValueError("suggest_threshold cannot exceed auto_threshold")

    # An explicit escalate recommendation always routes to a human, regardless of
    # confidence (e.g. an ambiguous trust boundary the model flagged).
    if recommended_action is Action.ESCALATE:
        return GovernanceDecision(
            disposition=Disposition.ESCALATE,
            requires_human=True,
            reason="Model recommended escalation (ambiguous/uncertain finding).",
            reason_code=ReasonCode.MODEL_ESCALATION,
        )

    # Auto-execution bar is action-dependent: suppression is held to a higher bar.
    if recommended_action is Action.SUPPRESS:
        if confidence >= suppress_auto_threshold:
            return GovernanceDecision(
                disposition=Disposition.AUTO_EXECUTE,
                requires_human=False,
                reason=(
                    f"Confidence {confidence:.2f} >= suppress auto threshold "
                    f"{suppress_auto_threshold:.2f}; auto-dismiss permitted."
                ),
                reason_code=ReasonCode.AUTO_SUPPRESS_HIGH_CONFIDENCE,
            )
        if confidence >= suggest_threshold:
            return GovernanceDecision(
                disposition=Disposition.HUMAN_APPROVAL,
                requires_human=True,
                reason=(
                    f"Suppression at confidence {confidence:.2f} is below the stricter "
                    f"auto-dismiss bar {suppress_auto_threshold:.2f}; needs human review."
                ),
                reason_code=ReasonCode.SUPPRESS_NEEDS_REVIEW,
            )
        return GovernanceDecision(
            disposition=Disposition.ESCALATE,
            requires_human=True,
            reason=f"Confidence {confidence:.2f} < suggest threshold {suggest_threshold:.2f}.",
            reason_code=ReasonCode.BELOW_SUGGEST_THRESHOLD,
        )

    # create_ticket (and any non-escalate action): standard auto threshold.
    if confidence >= auto_threshold:
        return GovernanceDecision(
            disposition=Disposition.AUTO_EXECUTE,
            requires_human=False,
            reason=f"Confidence {confidence:.2f} >= auto threshold {auto_threshold:.2f}.",
            reason_code=ReasonCode.AUTO_HIGH_CONFIDENCE,
        )
    if confidence >= suggest_threshold:
        return GovernanceDecision(
            disposition=Disposition.HUMAN_APPROVAL,
            requires_human=True,
            reason=(
                f"Confidence {confidence:.2f} in approval band "
                f"[{suggest_threshold:.2f}, {auto_threshold:.2f})."
            ),
            reason_code=ReasonCode.APPROVAL_BAND,
        )
    return GovernanceDecision(
        disposition=Disposition.ESCALATE,
        requires_human=True,
        reason=f"Confidence {confidence:.2f} < suggest threshold {suggest_threshold:.2f}.",
        reason_code=ReasonCode.BELOW_SUGGEST_THRESHOLD,
    )
