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
