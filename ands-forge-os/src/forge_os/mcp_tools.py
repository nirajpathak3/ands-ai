"""MCP tool logic for ANDS Forge OS — the headless engine exposed as agent-callable tools.

This module is the *logic* behind the MCP server (``mcp_server.py``), kept deliberately
free of any MCP/third-party dependency so it imports with the stdlib-only kernel and is
fully testable offline. Each function takes a ``Forge`` plus plain arguments and returns a
JSON-serializable dict — the same lifecycle the CLI and REST API drive, so a run started
from Cursor can be approved from the dashboard and vice versa (durable, keyed by ``run_id``).

Tools mirror PRODUCT-VISION §9: forge.start_run / status / approve / reject / get_artifact,
plus list/audit/blueprint for observability.
"""

from __future__ import annotations

from typing import Any

from forge_kernel.runner import Forge
from forge_kernel.state import RunState, RunStatus


def _summary(run: RunState) -> dict[str, Any]:
    """The compact run summary returned by lifecycle tools (mirrors the CLI/API shape)."""
    return {
        "runId": run.run_id,
        "status": str(run.status),
        "currentStage": run.current_stage,
        "costUsd": run.cost_usd,
        "pendingGate": run.pending_gate,
        "workspace": run.workspace_dir,
    }


def start_run(forge: Forge, vision: str) -> dict[str, Any]:
    """Start a run from a product vision. Runs autonomously until it completes or pauses
    at the first human-in-the-loop gate (then ``status`` is ``awaiting_approval``)."""
    if not vision or not vision.strip():
        return {"error": "vision must not be empty"}
    run = forge.start(vision.strip())
    return _summary(run)


def status(forge: Forge, run_id: str) -> dict[str, Any]:
    """Current status of a run: stage, cost, artifact statuses, and the pending gate (if any)."""
    try:
        return forge.status_summary(run_id)
    except KeyError:
        return {"error": f"unknown run {run_id}"}


def approve(forge: Forge, run_id: str, feedback: str = "") -> dict[str, Any]:
    """Approve the pending HITL gate and resume the run until the next gate or completion."""
    try:
        run = forge.get(run_id)
    except KeyError:
        return {"error": f"unknown run {run_id}"}
    if run.status != RunStatus.AWAITING_APPROVAL:
        return {"error": f"run is {run.status}, not awaiting approval", **_summary(run)}
    return _summary(forge.resume(run_id, approved=True, feedback=feedback))


def reject(forge: Forge, run_id: str, feedback: str = "") -> dict[str, Any]:
    """Reject the pending gate (reopens the stage with feedback, bounded re-iteration)."""
    try:
        run = forge.get(run_id)
    except KeyError:
        return {"error": f"unknown run {run_id}"}
    if run.status != RunStatus.AWAITING_APPROVAL:
        return {"error": f"run is {run.status}, not awaiting approval", **_summary(run)}
    return _summary(forge.resume(run_id, approved=False, feedback=feedback))


def get_artifact(forge: Forge, run_id: str, key: str) -> dict[str, Any]:
    """Fetch one produced artifact's content + review scores + on-disk path."""
    try:
        run = forge.get(run_id)
    except KeyError:
        return {"error": f"unknown run {run_id}"}
    record = run.artifacts.get(key)
    if record is None:
        return {"error": f"unknown artifact '{key}'",
                "available": sorted(run.artifacts.keys())}
    return record.to_dict()


def list_runs(forge: Forge) -> dict[str, Any]:
    """List all runs in the workspace with a one-line summary each."""
    runs = []
    for run_id in forge.store.list_runs():
        try:
            run = forge.get(run_id)
        except KeyError:
            continue
        runs.append({
            "runId": run.run_id, "status": str(run.status),
            "currentStage": run.current_stage, "costUsd": run.cost_usd,
            "vision": run.vision[:120],
        })
    return {"runs": runs}


def audit(forge: Forge, run_id: str) -> dict[str, Any]:
    """The append-only audit trail for a run (the 'why' behind every decision)."""
    if not forge.store.exists(run_id):
        return {"error": f"unknown run {run_id}"}
    return {"runId": run_id, "events": forge.audit_for(run_id)}


def blueprint(forge: Forge) -> dict[str, Any]:
    """The compiled lifecycle program: stages → artifacts → owning role → gate mode."""
    stages = []
    for s in forge.blueprint.ordered_stages():
        stages.append({
            "key": s.key, "title": s.title, "order": s.order,
            "gateMode": s.gate_mode or forge.settings.default_gate_mode,
            "autoPass": s.auto_pass,
            "artifacts": [{"key": a.key, "title": a.title, "role": a.role} for a in s.artifacts],
        })
    return {
        "name": forge.blueprint.name,
        "version": forge.blueprint.version,
        "mode": forge.settings.mode,
        "stages": stages,
    }
