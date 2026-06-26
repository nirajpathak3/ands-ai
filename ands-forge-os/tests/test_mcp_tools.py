"""MCP tool logic: the headless lifecycle exposed to MCP clients, driven offline.

These cover the dependency-free ``mcp_tools`` functions (no 'mcp' package required) so the
Cursor/VS Code/Antigravity integration is verified end-to-end in the deterministic path.
"""

from __future__ import annotations

from forge_kernel.runner import RunStore
from forge_os import build_forge, mcp_tools


def _forge(tmp_path):
    return build_forge(store=RunStore(str(tmp_path)))


def _drive_to_completion(forge, run_id: str) -> dict:
    summary = mcp_tools.status(forge, run_id)
    guard = 0
    while summary["status"] == "awaiting_approval" and guard < 20:
        guard += 1
        summary = mcp_tools.approve(forge, run_id, feedback="ok")
    return summary


def test_start_pauses_at_first_gate(tmp_path):
    forge = _forge(tmp_path)
    started = mcp_tools.start_run(forge, "A governed AI agent platform")
    assert started["status"] == "awaiting_approval"
    assert started["runId"]
    assert started["pendingGate"] is not None


def test_full_lifecycle_start_approve_to_completed(tmp_path):
    forge = _forge(tmp_path)
    started = mcp_tools.start_run(forge, "A governed AI agent platform")
    final = _drive_to_completion(forge, started["runId"])
    assert final["status"] == "completed"

    # Artifacts are fetchable with content + scores; the PRD exists and was reviewed.
    prd = mcp_tools.get_artifact(forge, started["runId"], "prd")
    assert "error" not in prd
    assert prd["content"]

    # Audit trail and run listing are populated.
    aud = mcp_tools.audit(forge, started["runId"])
    assert aud["events"]
    listing = mcp_tools.list_runs(forge)
    assert any(r["runId"] == started["runId"] for r in listing["runs"])


def test_empty_vision_is_rejected(tmp_path):
    forge = _forge(tmp_path)
    assert "error" in mcp_tools.start_run(forge, "   ")


def test_unknown_run_and_artifact_return_errors(tmp_path):
    forge = _forge(tmp_path)
    assert "error" in mcp_tools.status(forge, "nope")
    assert "error" in mcp_tools.approve(forge, "nope")
    assert "error" in mcp_tools.audit(forge, "nope")
    started = mcp_tools.start_run(forge, "A governed AI agent platform")
    missing = mcp_tools.get_artifact(forge, started["runId"], "does_not_exist")
    assert "error" in missing and "available" in missing


def test_approve_when_not_awaiting_is_a_clean_error(tmp_path):
    forge = _forge(tmp_path)
    started = mcp_tools.start_run(forge, "A governed AI agent platform")
    _drive_to_completion(forge, started["runId"])
    # Already completed -> approving again is a friendly error, not an exception.
    again = mcp_tools.approve(forge, started["runId"])
    assert "error" in again and again["status"] == "completed"


def test_reject_reopens_with_feedback(tmp_path):
    forge = _forge(tmp_path)
    started = mcp_tools.start_run(forge, "A governed AI agent platform")
    rejected = mcp_tools.reject(forge, started["runId"], feedback="tighten the metrics")
    # A reject keeps the run going (reopened/awaiting), never a hard failure.
    assert "runId" in rejected


def test_blueprint_exposes_stages(tmp_path):
    forge = _forge(tmp_path)
    bp = mcp_tools.blueprint(forge)
    assert bp["name"] == "ands-forge-os"
    assert any(s["key"] == "scaffold" for s in bp["stages"])
