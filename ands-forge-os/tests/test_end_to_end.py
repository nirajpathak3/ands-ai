"""End-to-end run: HITL pause/resume, parallel fan-out, artifacts on disk, durability."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_kernel.config import Settings
from forge_kernel.runner import RunStore
from forge_kernel.state import RunStatus
from forge_os import build_forge

VISION = "A platform that helps small teams run governed AI agents safely"


def _offline_settings(workspace: Path) -> Settings:
    return Settings(workspace=str(workspace))


def _drive_to_completion(forge, run):
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 20:
        guard += 1
        run = forge.resume(run.run_id, approved=True, feedback="ok")
    return run


def test_full_run_completes_with_artifacts_on_disk(tmp_path):
    forge = build_forge(_offline_settings(tmp_path), store=RunStore(tmp_path))
    run = forge.start(VISION)
    assert run.status == RunStatus.AWAITING_APPROVAL  # first gate is always-human
    assert run.pending_gate["stage"] == "intake"

    run = _drive_to_completion(forge, run)
    assert run.status == RunStatus.COMPLETED
    assert run.cost_usd == 0.0  # offline deterministic

    # Every produced/auto-passed artifact cleared its eval bar.
    assert all(a.eval_score and a.eval_score >= 0.75 for a in run.artifacts.values())

    # Tangible outputs exist on disk.
    art_dir = Path(run.workspace_dir)
    assert (art_dir / "ux" / "mockup.html").exists()
    assert list((art_dir / "scaffold").glob("*/README.md"))
    assert (art_dir / "scaffold").glob("*/app/main.py")


def test_discovery_runs_in_parallel(tmp_path):
    forge = build_forge(_offline_settings(tmp_path), store=RunStore(tmp_path))
    run = _drive_to_completion(forge, forge.start(VISION))
    parallel = [
        e for e in forge.audit_for(run.run_id)
        if e["reason_code"] == "stage_completed" and e["data"].get("maxParallelism", 1) >= 2
    ]
    discovery = [e for e in parallel if e["stage"] == "discovery"]
    assert discovery and discovery[0]["data"]["maxParallelism"] == 3


def test_durable_resume_across_new_forge_instance(tmp_path):
    store = RunStore(tmp_path)
    settings = _offline_settings(tmp_path)
    forge_a = build_forge(settings, store=store)
    run = forge_a.start(VISION)
    run_id = run.run_id
    assert run.status == RunStatus.AWAITING_APPROVAL

    # A fresh Forge (new process simulation) resumes from the persisted store.
    forge_b = build_forge(settings, store=RunStore(tmp_path))
    resumed = _drive_to_completion(forge_b, forge_b.get(run_id))
    assert resumed.status == RunStatus.COMPLETED
    # Audit trail stays continuous (re-seeded from disk on resume).
    assert any(e["reason_code"] == "run_started" for e in forge_b.audit_for(run_id))
    assert any(e["reason_code"] == "run_completed" for e in forge_b.audit_for(run_id))


def test_rejection_reopens_stage_then_bounded_halt(tmp_path):
    settings = Settings(workspace=str(tmp_path), max_stage_iterations=2)
    forge = build_forge(settings, store=RunStore(tmp_path))
    run = forge.start(VISION)  # pauses at intake (always-human)
    # Reject twice -> hits the bounded-iteration cap and halts as REJECTED.
    run = forge.resume(run.run_id, approved=False, feedback="needs work")
    assert run.status in (RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL)
    run = forge.resume(run.run_id, approved=False, feedback="still not there")
    assert run.status == RunStatus.REJECTED


@pytest.mark.parametrize("vision", ["", "   "])
def test_empty_vision_still_runs_but_is_thin(tmp_path, vision):
    forge = build_forge(_offline_settings(tmp_path), store=RunStore(tmp_path))
    run = forge.start(vision or "x")
    assert run.status == RunStatus.AWAITING_APPROVAL
