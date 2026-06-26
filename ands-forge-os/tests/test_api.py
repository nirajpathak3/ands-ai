"""FastAPI edge: start -> approve gates -> completed, plus mockup + audit endpoints."""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the app's workspace at a temp dir BEFORE importing it (settings read at import).
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import forge_os.api as api

    importlib.reload(api)
    return TestClient(api.app)


def test_health_and_blueprint(client):
    assert client.get("/health").json()["status"] == "ok"
    bp = client.get("/blueprint").json()
    assert bp["name"] == "ands-forge-os"
    assert any(s["key"] == "scaffold" for s in bp["stages"])


def test_start_approve_flow_to_completion(client):
    started = client.post("/runs", json={"vision": "A governed AI agent platform"}).json()
    run_id = started["runId"]
    assert started["status"] == "awaiting_approval"

    status = started
    guard = 0
    while status["status"] == "awaiting_approval" and guard < 20:
        guard += 1
        status = client.post(f"/runs/{run_id}/approve", json={"feedback": "ok"}).json()
    assert status["status"] == "completed"

    # Mockup is served as HTML.
    mock = client.get(f"/runs/{run_id}/mockup")
    assert mock.status_code == 200
    assert "<html" in mock.text.lower()

    # Audit trail is non-trivial.
    audit = client.get(f"/runs/{run_id}/audit").json()["events"]
    assert any(e["reason_code"] == "run_completed" for e in audit)


def test_models_map_endpoint(client):
    data = client.get("/models").json()
    assert data["tiers"]["strong"] and data["tiers"]["cheap"]
    # The technical (architecture) stage's artifacts resolve to the strong tier by default.
    arch = next(s for s in data["stages"] if s["key"] == "technical")
    assert all(a["tier"] in ("strong", "pinned") for a in arch["artifacts"])
    # A drafting stage resolves to the cheap tier.
    disc = next(s for s in data["stages"] if s["key"] == "discovery")
    assert any(a["tier"] == "cheap" for a in disc["artifacts"])
    # The judge always resolves to the strong tier.
    assert all(a["judgeModel"] == data["tiers"]["strong"]
               for s in data["stages"] for a in s["artifacts"]
               if a["tier"] != "auto-pass")


def test_models_view_overlays_run_cost(client):
    run_id = client.post("/runs", json={"vision": "X"}).json()["runId"]
    guard = 0
    status = {"status": "awaiting_approval"}
    while status["status"] == "awaiting_approval" and guard < 20:
        guard += 1
        status = client.post(f"/runs/{run_id}/approve", json={}).json()
    view = client.get(f"/models/view?run_id={run_id}")
    assert view.status_code == 200 and "Model map" in view.text
    j = client.get(f"/models?run_id={run_id}").json()
    assert j["runId"] == run_id
    assert any(s["stageCostUsd"] is not None for s in j["stages"])


def test_empty_vision_rejected(client):
    assert client.post("/runs", json={"vision": "  "}).status_code == 400


def test_unknown_run_404(client):
    assert client.get("/runs/nope").status_code == 404
