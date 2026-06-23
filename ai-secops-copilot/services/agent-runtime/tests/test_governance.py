"""Tests for the confidence-gated governance logic (pure, no heavy deps)."""

import pytest

from app.domain import Action, Disposition
from app.governance import GovernancePolicy, ReasonCode, evaluate


def test_high_confidence_auto_executes():
    d = evaluate(0.95, Action.CREATE_TICKET)
    assert d.disposition is Disposition.AUTO_EXECUTE
    assert d.requires_human is False
    assert d.reason_code is ReasonCode.AUTO_HIGH_CONFIDENCE


def test_mid_band_requires_human_approval():
    d = evaluate(0.71, Action.CREATE_TICKET)
    assert d.disposition is Disposition.HUMAN_APPROVAL
    assert d.requires_human is True


def test_low_confidence_escalates():
    d = evaluate(0.40, Action.CREATE_TICKET)
    assert d.disposition is Disposition.ESCALATE
    assert d.requires_human is True


def test_boundary_at_auto_threshold_is_inclusive():
    assert evaluate(0.90, Action.CREATE_TICKET).disposition is Disposition.AUTO_EXECUTE


def test_boundary_at_suggest_threshold_is_inclusive():
    assert evaluate(0.60, Action.CREATE_TICKET).disposition is Disposition.HUMAN_APPROVAL


def test_explicit_escalate_action_overrides_high_confidence():
    d = evaluate(0.99, Action.ESCALATE)
    assert d.disposition is Disposition.ESCALATE
    assert d.requires_human is True
    assert d.reason_code is ReasonCode.MODEL_ESCALATION


def test_invalid_confidence_raises():
    with pytest.raises(ValueError):
        evaluate(1.5, Action.CREATE_TICKET)


# --- asymmetric auto-suppress policy (Day 7) ---------------------------------

def test_suppress_below_strict_bar_needs_review():
    # 0.92 auto-creates a ticket, but is NOT enough to auto-DISMISS a finding.
    assert evaluate(0.92, Action.CREATE_TICKET).disposition is Disposition.AUTO_EXECUTE
    d = evaluate(0.92, Action.SUPPRESS)
    assert d.disposition is Disposition.HUMAN_APPROVAL
    assert d.reason_code is ReasonCode.SUPPRESS_NEEDS_REVIEW


def test_suppress_above_strict_bar_auto_executes():
    d = evaluate(0.96, Action.SUPPRESS)
    assert d.disposition is Disposition.AUTO_EXECUTE
    assert d.reason_code is ReasonCode.AUTO_SUPPRESS_HIGH_CONFIDENCE


def test_suppress_below_suggest_escalates():
    d = evaluate(0.40, Action.SUPPRESS)
    assert d.disposition is Disposition.ESCALATE
    assert d.reason_code is ReasonCode.BELOW_SUGGEST_THRESHOLD


def test_policy_object_is_honored():
    policy = GovernancePolicy(
        auto_threshold=0.8, suggest_threshold=0.5, suppress_auto_threshold=0.99
    )
    ticket = evaluate(0.85, Action.CREATE_TICKET, policy=policy)
    suppress = evaluate(0.85, Action.SUPPRESS, policy=policy)
    assert ticket.disposition is Disposition.AUTO_EXECUTE
    assert suppress.disposition is Disposition.HUMAN_APPROVAL


def test_policy_validation_rejects_bad_thresholds():
    with pytest.raises(ValueError):
        GovernancePolicy(auto_threshold=0.5, suggest_threshold=0.9)
