"""Eval-as-gate harness: aggregate stage scores + a reusable regression gate.

The per-artifact eval signal is produced by the cross-cutting ``Reviewer`` (Critic +
red-team). This module aggregates those into a stage score (the gate input) and provides
a small ``RegressionGate`` the CI eval harness uses to fail the build when run quality
drops below thresholds — the same "eval-as-gate + CI" pattern from ai-secops-copilot.
"""

from __future__ import annotations

from .rubric import RegressionGate, aggregate_eval

__all__ = ["aggregate_eval", "RegressionGate"]
