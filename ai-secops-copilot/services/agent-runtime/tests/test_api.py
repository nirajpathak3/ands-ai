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


def test_metrics_includes_decision_events():
    assert "decisionEvents" in client.get("/metrics").json()


def test_reseeding_dedupes_findings_but_appends_events():
    client.post("/demo/reset")
    first = client.post("/demo/seed").json()
    after_first = client.get("/metrics").json()
    client.post("/demo/seed")
    after_second = client.get("/metrics").json()

    # Current-state findings are deduped -> the count is stable across re-seeds...
    assert after_second["findingsProcessed"] == after_first["findingsProcessed"]
    # ...while the append-only audit (decision events) grows...
    assert after_second["decisionEvents"] == 2 * after_first["decisionEvents"]
    # ...and idempotent ticket creation means no duplicate tickets.
    assert after_second["ticketsCreated"] == after_first["ticketsCreated"]
    assert "semgrep-sample.json" in first["seeded"]


def test_findings_view_dedupes_and_links_tickets():
    client.post("/demo/reset")
    client.post("/demo/seed")
    one = client.get("/findings").json()
    client.post("/demo/seed")
    two = client.get("/findings").json()

    # Same set of findings, no duplicate rows on re-seed.
    assert two["count"] == one["count"]
    # Re-evaluation is visible as a counter, not a new row.
    assert max(f["evaluations"] for f in two["findings"]) >= 2
    # At least one finding carries a linked ticket (the critical SQLi).
    assert any(f["ticket"] for f in two["findings"])


def test_escalation_queue_is_idempotent_across_reseeds():
    client.post("/demo/reset")
    client.post("/demo/seed")
    first = client.get("/escalations").json()["count"]
    client.post("/demo/seed")
    second = client.get("/escalations").json()["count"]
    assert first == second  # re-escalating the same finding does not duplicate


def test_demo_reset_clears_state():
    client.post("/demo/seed")
    assert client.get("/metrics").json()["findingsProcessed"] > 0
    assert client.post("/demo/reset").json()["status"] == "reset"
    cleared = client.get("/metrics").json()
    assert cleared["findingsProcessed"] == 0
    assert cleared["ticketsCreated"] == 0


# --- Day 12: observability ---------------------------------------------------

def test_prometheus_metrics_exposition():
    client.post("/demo/reset")
    client.post("/demo/seed")
    resp = client.get("/observability/metrics")
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "# TYPE secops_llm_requests_total counter" in body
    assert "secops_findings_processed" in body


def test_observability_timeseries_and_traces_after_seed():
    client.post("/demo/reset")
    client.post("/demo/seed")
    ts = client.get("/observability/timeseries").json()
    assert ts["recentLlm"]  # gateway calls were recorded
    traces = client.get("/observability/traces").json()
    assert any(s["name"] == "pipeline.run" for s in traces["spans"])


def test_alerts_endpoint_and_health_block():
    client.post("/demo/reset")
    alerts = client.get("/observability/alerts").json()
    assert alerts["count"] == 0  # healthy, empty slate
    health = client.get("/health").json()
    assert health["observability"]["tracing"] in ("in-process", "otel")
    assert health["observability"]["alertsFiring"] == 0
