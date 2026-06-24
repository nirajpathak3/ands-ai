"""Day 19: policy-as-code & suppression rules."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.policy import PolicyEngine, PolicyRule, build_engine, parse_rules

client = TestClient(app)

_SQLI = {
    "id": "F-POL-1", "ruleId": "formatted-sql-query", "title": "SQLi",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}


def _rule(**kw) -> PolicyRule:
    return PolicyRule.from_dict({"id": "r1", "action": "suppress", **kw})


# --- rule parsing -----------------------------------------------------------

def test_from_dict_validates_action_and_id():
    with pytest.raises(ValueError):
        PolicyRule.from_dict({"id": "x", "action": "bogus"})
    with pytest.raises(ValueError):
        PolicyRule.from_dict({"id": "", "action": "suppress"})


def test_parse_rules_list():
    rules = parse_rules([{"id": "a", "action": "force_escalate", "severity": ["high"]}])
    assert rules[0].id == "a" and rules[0].severity == ("high",)


# --- matching ---------------------------------------------------------------

def test_match_by_severity():
    eng = PolicyEngine([_rule(severity=["critical"])])
    assert eng.match(_SQLI, "critical") is not None
    assert eng.match(_SQLI, "low") is None


def test_match_by_rule_id_or_cwe():
    assert PolicyEngine([_rule(ruleIds=["formatted-sql-query"])]).match(_SQLI, "high")
    assert PolicyEngine([_rule(ruleIds=["CWE-89"])]).match(_SQLI, "high")
    assert PolicyEngine([_rule(ruleIds=["other"])]).match(_SQLI, "high") is None


def test_match_by_path_glob():
    assert PolicyEngine([_rule(paths=["app/api/**"])]).match(_SQLI, "high")
    assert PolicyEngine([_rule(paths=["tests/**"])]).match(_SQLI, "high") is None


def test_first_match_wins():
    eng = PolicyEngine([
        PolicyRule.from_dict({"id": "first", "action": "force_escalate"}),
        PolicyRule.from_dict({"id": "second", "action": "suppress"}),
    ])
    assert eng.match(_SQLI, "high").id == "first"


def test_disabled_rule_skipped():
    eng = PolicyEngine([_rule(enabled=False)])
    assert eng.match(_SQLI, "critical") is None


# --- apply / overrides ------------------------------------------------------

def _decision(severity="critical", action="create_ticket"):
    return {
        "findingId": "F-POL-1", "findingHash": "h",
        "analysis": {"severity": severity, "confidence": 0.99, "recommendedAction": action},
        "disposition": "auto_execute", "requiresHuman": False,
        "reasonCode": "auto_high_confidence",
    }


def test_apply_suppress_overrides_decision():
    eng = PolicyEngine([_rule(id="sup", ruleIds=["formatted-sql-query"])])
    d = _decision()
    match = eng.apply(_SQLI, d)
    assert match.action == "suppress"
    assert d["disposition"] == "auto_execute"
    assert d["analysis"]["recommendedAction"] == "suppress"
    assert d["reasonCode"] == "policy:sup"
    assert d["policyApplied"]["ruleId"] == "sup"
    assert eng.hits()["sup"] == 1


def test_apply_force_escalate():
    eng = PolicyEngine([PolicyRule.from_dict({"id": "esc", "action": "force_escalate"})])
    d = _decision()
    eng.apply(_SQLI, d)
    assert d["disposition"] == "escalate"
    assert d["requiresHuman"] is True


def test_apply_annotate_keeps_disposition():
    eng = PolicyEngine([PolicyRule.from_dict({"id": "note", "action": "annotate"})])
    d = _decision()
    eng.apply(_SQLI, d)
    assert d["disposition"] == "auto_execute"
    assert d["reasonCode"] == "auto_high_confidence"  # unchanged
    assert d["policyApplied"]["action"] == "annotate"


def test_apply_no_match_returns_none():
    eng = PolicyEngine([_rule(paths=["nowhere/**"])])
    assert eng.apply(_SQLI, _decision()) is None


def test_build_engine_filters_by_tenant(monkeypatch):
    from app.config import Settings

    rules_json = (
        '[{"id":"all","action":"suppress"},'
        '{"id":"only-b","action":"suppress","tenants":["tenant-b"]}]'
    )
    settings = Settings(policy_rules_inline=rules_json)
    a = build_engine(settings, "tenant-a")
    b = build_engine(settings, "tenant-b")
    assert {r.id for r in a.rules} == {"all"}
    assert {r.id for r in b.rules} == {"all", "only-b"}


# --- API --------------------------------------------------------------------

_H = {"X-Tenant-Id": "policy-api"}


def test_set_and_get_policy_rules():
    client.post("/demo/reset", headers=_H)
    body = client.post(
        "/policy/rules",
        json={"rules": [{"id": "sup-sqli", "action": "suppress",
                         "ruleIds": ["formatted-sql-query"], "reason": "known FP pattern"}]},
        headers=_H,
    ).json()
    assert body["count"] == 1
    got = client.get("/policy", headers=_H).json()
    assert got["rules"][0]["id"] == "sup-sqli"


def test_policy_suppresses_in_pipeline():
    client.post("/demo/reset", headers=_H)
    client.post(
        "/policy/rules",
        json={"rules": [{"id": "sup-sqli", "action": "suppress",
                         "ruleIds": ["formatted-sql-query"]}]},
        headers=_H,
    )
    out = client.post("/analyze", json={"finding": _SQLI}, headers=_H).json()
    assert out["decision"]["disposition"] == "auto_execute"
    assert out["decision"]["reasonCode"] == "policy:sup-sqli"
    assert out["action"]["outcome"] == "suppressed"

    # hit count is tracked
    assert client.get("/policy", headers=_H).json()["hits"]["sup-sqli"] >= 1


def test_policy_evaluate_dry_run():
    client.post("/demo/reset", headers=_H)
    client.post(
        "/policy/rules",
        json={"rules": [{"id": "esc-auth", "action": "force_escalate",
                         "paths": ["app/api/**"]}]},
        headers=_H,
    )
    res = client.post(
        "/policy/evaluate", json={"finding": _SQLI, "severity": "high"}, headers=_H
    ).json()
    assert res["matched"] is True
    assert res["rule"]["id"] == "esc-auth"
    # dry-run does not increment hits
    assert client.get("/policy", headers=_H).json()["hits"]["esc-auth"] == 0


def test_invalid_rules_rejected():
    res = client.post(
        "/policy/rules", json={"rules": [{"id": "bad", "action": "nope"}]}, headers=_H
    )
    assert res.status_code == 400
