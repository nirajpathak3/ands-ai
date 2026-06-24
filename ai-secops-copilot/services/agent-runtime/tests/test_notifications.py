"""Day 17: notifications (outbound channels) & webhooks (inbound lifecycle sync)."""

from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.notifications import (
    Notification,
    NotificationCenter,
    SlackChannel,
    WebhookChannel,
    normalize_status,
    parse_ticket_webhook,
    sign,
    verify_signature,
)

client = TestClient(app)

_CRITICAL = {
    "id": "F-NOTIF-1", "ruleId": "formatted-sql-query", "title": "SQLi",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}


def _note(event="escalation", fh="abc"):
    return Notification(timestamp="t", event=event, severity="warning",
                        title="x", message="y", findingHash=fh, findingId="F-1")


# --- signatures -------------------------------------------------------------

def test_signature_roundtrip():
    body = b'{"a":1}'
    sig = sign("secret", body)
    assert verify_signature("secret", body, "sha256=" + sig)
    assert verify_signature("secret", body, sig)  # bare hex also accepted


def test_signature_open_when_no_secret():
    assert verify_signature("", b"anything", None) is True


def test_signature_rejects_bad_or_missing():
    assert verify_signature("secret", b"body", None) is False
    assert verify_signature("secret", b"body", "sha256=deadbeef") is False


# --- inbound payload parsing ------------------------------------------------

def test_normalize_status_aliases():
    assert normalize_status("Done") == "done"
    assert normalize_status("In Progress") == "in_progress"
    assert normalize_status("Resolved") == "resolved"
    assert normalize_status("bogus") is None


def test_parse_generic_jira_servicenow():
    fh, st, tn = parse_ticket_webhook({"findingHash": "h1", "status": "resolved", "tenant": "t1"})
    assert (fh, st, tn) == ("h1", "resolved", "t1")

    jira = {"issue": {"fields": {"labels": ["secops-managed", "finding-h2"],
                                 "status": {"name": "Done"}}}}
    assert parse_ticket_webhook(jira)[:2] == ("h2", "done")

    snow = {"correlation_id": "h3", "state": "Closed"}
    assert parse_ticket_webhook(snow)[:2] == ("h3", "closed")


# --- NotificationCenter -----------------------------------------------------

class _Recorder:
    name = "rec"

    def __init__(self):
        self.sent = []

    def send(self, n):
        self.sent.append(n)
        return {"channel": self.name, "ok": True}


def test_center_dispatch_and_dedupe():
    rec = _Recorder()
    center = NotificationCenter([rec])
    first = center.emit("escalation", title="t", message="m", finding_hash="h")
    second = center.emit("escalation", title="t", message="m", finding_hash="h")  # deduped
    assert first is not None and second is None
    assert len(rec.sent) == 1
    assert center.channels == ["rec"]
    assert len(center.list_recent()) == 1


def test_center_disabled_emits_nothing():
    rec = _Recorder()
    center = NotificationCenter([rec], enabled=False)
    assert center.emit("escalation", title="t", message="m", finding_hash="h") is None
    assert rec.sent == []


def test_center_channel_failure_is_isolated():
    class _Boom:
        name = "boom"

        def send(self, n):
            raise RuntimeError("down")

    center = NotificationCenter([_Boom()])
    n = center.emit("sla_breach", title="t", message="m", finding_hash="h")
    assert n is not None and n.delivery[0]["ok"] is False


# --- channels over a mocked transport --------------------------------------

def test_webhook_channel_signs_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["sig"] = request.headers.get("X-Signature")
        return httpx.Response(200)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    res = WebhookChannel("http://hook.local/x", secret="s", client=http).send(_note())
    assert res["ok"] and res["status"] == 200
    assert verify_signature("s", captured["body"], captured["sig"])


def test_slack_channel_posts_text():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    res = SlackChannel("http://slack.local/x", client=http).send(_note())
    assert res["ok"]
    assert "text" in captured["body"]


# --- API: outbound on decisions --------------------------------------------

_H = {"X-Tenant-Id": "notif-api"}


def test_seed_emits_approval_or_escalation():
    client.post("/demo/reset", headers=_H)
    client.post("/demo/seed", headers=_H)
    body = client.get("/notifications", headers=_H).json()
    assert "log" in body["channels"]
    events = {n["event"] for n in body["notifications"]}
    assert events & {"approval_required", "escalation"}


# --- API: inbound webhook ---------------------------------------------------

def _seed_ticket(headers) -> str:
    client.post("/demo/reset", headers=headers)
    decision = client.post(
        "/analyze", json={"finding": _CRITICAL}, headers=headers
    ).json()["decision"]
    return decision["findingHash"]


def test_webhook_resolves_ticket_and_notifies():
    h = _seed_ticket(_H)
    res = client.post(
        "/webhooks/tickets",
        json={"findingHash": h, "status": "resolved", "tenant": "notif-api"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["resolved"] is True and body["tenant"] == "notif-api"

    findings = client.get("/findings", headers=_H).json()["findings"]
    target = next(f for f in findings if f["findingHash"] == h)
    assert target["outcome"] == "ticket_resolved"

    events = {n["event"] for n in client.get("/notifications", headers=_H).json()["notifications"]}
    assert "ticket_resolved" in events


def test_webhook_unknown_finding_404():
    res = client.post("/webhooks/tickets", json={"findingHash": "nope", "status": "resolved"})
    assert res.status_code == 404


def test_webhook_bad_payload_400():
    res = client.post("/webhooks/tickets", json={"status": "resolved"})  # no hash
    assert res.status_code == 400


def test_webhook_hmac_enforced_when_secret_set():
    h = _seed_ticket(_H)
    payload = json.dumps({"findingHash": h, "status": "resolved", "tenant": "notif-api"}).encode()
    app.dependency_overrides[get_settings] = lambda: Settings(webhook_secret="topsecret")
    try:
        unsigned = client.post("/webhooks/tickets", content=payload,
                               headers={"Content-Type": "application/json"})
        assert unsigned.status_code == 401

        signed = client.post(
            "/webhooks/tickets", content=payload,
            headers={"Content-Type": "application/json",
                     "X-Signature": "sha256=" + sign("topsecret", payload)},
        )
        assert signed.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_sweep_no_breaches_offline():
    client.post("/demo/reset", headers=_H)
    client.post("/demo/seed", headers=_H)
    # Fresh tickets are well within SLA, so no breaches fire.
    assert client.post("/notifications/sweep", headers=_H).json()["breaches"] == 0
