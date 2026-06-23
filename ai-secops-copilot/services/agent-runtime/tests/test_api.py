"""API-level tests (FastAPI TestClient): governance reason codes + audit trail."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_CRITICAL = {
    "id": "F-API-1", "ruleId": "formatted-sql-query", "title": "SQLi",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}


def test_health_exposes_governance_and_knowledge():
    body = client.get("/health").json()
    assert body["governance"]["suppressAutoThreshold"] >= body["governance"]["autoThreshold"]
    assert body["knowledge"]["ragEnabled"] in (True, False)


def test_governance_preview_returns_reason_code():
    body = client.post(
        "/governance/preview", json={"confidence": 0.95, "recommendedAction": "create_ticket"}
    ).json()
    assert body["disposition"] == "auto_execute"
    assert body["reasonCode"] == "auto_high_confidence"


def test_analyze_records_audit_with_reason_code():
    before = client.get("/audit").json()["count"]
    decision = client.post("/analyze", json={"finding": _CRITICAL}).json()["decision"]
    assert decision["reasonCode"] == "auto_high_confidence"

    audit = client.get("/audit").json()
    assert audit["count"] == before + 1
    last = audit["records"][-1]
    assert last["findingId"] == "F-API-1"
    assert last["actor"] == "system"
    assert last["disposition"] == "auto_execute"
    assert last["reasonCode"] == "auto_high_confidence"
    assert last["latencyMs"] >= 0.0


# --- Day 8: dashboard, metrics, demo seed ------------------------------------

def test_dashboard_served_as_html():
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "AI Security Operations Copilot" in res.text


def test_root_redirects_to_dashboard():
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (307, 308)
    assert res.headers["location"] == "/dashboard"


def test_metrics_shape_and_rates_bounded():
    m = client.get("/metrics").json()
    for key in ("findingsProcessed", "ticketsCreated", "rates", "latencyMs"):
        assert key in m
    for rate in m["rates"].values():
        assert 0.0 <= rate <= 1.0


def test_demo_seed_then_metrics_reflect_processing():
    seed = client.post("/demo/seed").json()
    assert seed["seeded"]
    m = client.get("/metrics").json()
    assert m["findingsProcessed"] > 0
    # The bundled samples include a critical SQLi -> at least one auto-executed ticket.
    assert m["byDisposition"].get("auto_execute", 0) >= 1
