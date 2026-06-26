"""Parallel scheduler: topological waves + budget governor."""

from __future__ import annotations

import pytest

from forge_kernel.blueprint import ArtifactSpec
from forge_kernel.scheduler import (
    Budget,
    BudgetExceededError,
    ParallelScheduler,
    topological_waves,
)


def _spec(key: str, deps=()) -> ArtifactSpec:
    return ArtifactSpec(key=key, title=key, role=key, stage="s", depends_on=tuple(deps))


def test_independent_artifacts_form_one_parallel_wave():
    waves = topological_waves([_spec("a"), _spec("b"), _spec("c")])
    assert len(waves) == 1
    assert {s.key for s in waves[0]} == {"a", "b", "c"}


def test_dependencies_split_into_ordered_waves():
    waves = topological_waves([_spec("a"), _spec("b", ["a"]), _spec("c", ["b"])])
    assert [[s.key for s in w] for w in waves] == [["a"], ["b"], ["c"]]


def test_scheduler_runs_and_reports_parallelism():
    sched = ParallelScheduler(max_concurrency=4)
    budget = Budget(max_usd=1.0, max_wall_seconds=60)
    stage_run = sched.run_stage(
        "discovery", [_spec("a"), _spec("b"), _spec("c")],
        execute_fn=lambda spec: {"key": spec.key}, budget=budget,
    )
    assert stage_run.max_parallelism == 3
    assert set(stage_run.results) == {"a", "b", "c"}


def test_budget_governor_blocks_overspend():
    budget = Budget(max_usd=0.10, max_wall_seconds=60, spent_usd=0.09)
    budget.check()  # ok
    with pytest.raises(BudgetExceededError):
        budget.check(about_to_spend=0.05)
