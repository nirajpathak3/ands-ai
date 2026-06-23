"""Tests for the ticket providers and selection (Jira via mocked HTTP transport).

No live Jira or credentials required: the Jira adapter takes an injectable httpx
client backed by httpx.MockTransport that simulates search + create with real
idempotency semantics.
"""

import json

import httpx
import pytest

from app.config import Settings
from app.providers import (
    JiraError,
    JiraTicketProvider,
    ServiceNowTicketProvider,
    get_ticket_provider,
)
from app.ticketing import (
    ApprovalStore,
    DeadLetterQueue,
    EscalationQueue,
    MockTicketProvider,
    execute_decision,
)


def _decision(finding_hash="h1", finding_id="F-1", severity="critical",
              disposition="auto_execute", action="create_ticket"):
    return {
        "findingId": finding_id,
        "findingHash": finding_hash,
        "analysis": {"severity": severity, "reason": "r", "recommendedAction": action},
        "disposition": disposition,
        "requiresHuman": disposition != "auto_execute",
        "governanceReason": "g",
    }


# --- Jira adapter (mocked transport) -------------------------------------------

def _jira_with_fake(fail_create=False):
    """A JiraTicketProvider wired to an in-memory fake Jira (search + create)."""
    state = {"issues": [], "counter": 0, "search_calls": 0, "create_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search/jql":
            state["search_calls"] += 1
            jql = json.loads(request.content)["jql"]
            found = [i for i in state["issues"] if i["label"] in jql]
            issues = [{"key": found[0]["key"]}] if found else []
            return httpx.Response(200, json={"issues": issues})
        if request.url.path == "/rest/api/3/issue":
            state["create_calls"] += 1
            if fail_create:
                return httpx.Response(500, json={"errorMessages": ["boom"]})
            labels = json.loads(request.content)["fields"]["labels"]
            hash_label = next(label for label in labels if label.startswith("finding-"))
            state["counter"] += 1
            key = f"SEC-{state['counter']}"
            state["issues"].append({"key": key, "label": hash_label})
            return httpx.Response(201, json={"key": key, "id": "1000"})
        return httpx.Response(404)

    client = httpx.Client(
        base_url="https://example.atlassian.net",
        transport=httpx.MockTransport(handler),
        auth=("e@x.com", "token"),
    )
    provider = JiraTicketProvider(
        base_url="https://example.atlassian.net", email="e@x.com",
        api_token="token", project_key="SEC", client=client,
    )
    return provider, state


def test_jira_create_issue():
    provider, state = _jira_with_fake()
    ticket, created = provider.create(_decision(), via="auto")
    assert created is True
    assert ticket.key == "SEC-1"
    assert ticket.provider == "jira"
    assert state["create_calls"] == 1


def test_jira_create_is_idempotent():
    provider, state = _jira_with_fake()
    t1, c1 = provider.create(_decision(), via="auto")
    t2, c2 = provider.create(_decision(), via="auto")  # same finding hash
    assert c1 is True and c2 is False
    assert t1.key == t2.key
    assert state["create_calls"] == 1  # second call found the existing issue, no POST


def test_jira_requires_credentials():
    with pytest.raises(ValueError):
        JiraTicketProvider(base_url="", email="", api_token="", project_key="")


def test_jira_api_failure_is_dead_lettered():
    provider, _ = _jira_with_fake(fail_create=True)
    # Direct call raises…
    with pytest.raises(JiraError):
        provider.create(_decision(), via="auto")
    # …and through the orchestrator it is dead-lettered, not lost.
    dlq = DeadLetterQueue()
    result = execute_decision(
        _decision(), provider=provider, approvals=ApprovalStore(),
        escalations=EscalationQueue(), dead_letter=dlq,
    )
    assert result.outcome == "ticket_failed"
    assert len(dlq.list_all()) == 1


# --- ServiceNow mock adapter ---------------------------------------------------

def test_servicenow_create_and_idempotency():
    provider = ServiceNowTicketProvider()
    t1, c1 = provider.create(_decision(severity="high"), via="auto")
    t2, c2 = provider.create(_decision(severity="high"), via="auto")
    assert c1 is True and c2 is False
    assert t1.key.startswith("INC")
    assert t1.provider == "servicenow"
    # incident record carries the finding hash as the correlation id (idempotency anchor)
    record = next(iter(provider.records.values()))
    assert record["correlation_id"] == "h1"


# --- factory selection ---------------------------------------------------------

def test_factory_defaults_to_mock():
    assert get_ticket_provider(Settings(ticket_provider="mock")).name == "mock"
    assert isinstance(get_ticket_provider(Settings(ticket_provider="mock")), MockTicketProvider)


def test_factory_selects_servicenow():
    assert get_ticket_provider(Settings(ticket_provider="servicenow")).name == "servicenow"


def test_factory_jira_without_creds_falls_back_to_mock():
    assert get_ticket_provider(Settings(ticket_provider="jira")).name == "mock"


def test_factory_selects_jira_with_creds():
    settings = Settings(
        ticket_provider="jira", jira_base_url="https://x.atlassian.net",
        jira_email="e@x.com", jira_api_token="t", jira_project_key="SEC",
    )
    assert get_ticket_provider(settings).name == "jira"
