"""Tests for the confidence-gated governance logic (pure, no heavy deps)."""

import pytest

from app.domain import Action, Disposition
from app.governance import evaluate


def test_high_confidence_auto_executes():
    d = evaluate(0.95, Action.CREATE_TICKET)
    assert d.disposition is Disposition.AUTO_EXECUTE
    assert d.requires_human is False


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


def test_invalid_confidence_raises():
    with pytest.raises(ValueError):
        evaluate(1.5, Action.CREATE_TICKET)
