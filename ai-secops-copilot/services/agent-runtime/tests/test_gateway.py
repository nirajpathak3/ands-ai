"""Tests for the Day-11 AI Gateway: routing, semantic cache, fallback, cost, metrics."""

import json

from app.config import Settings
from app.gateway import (
    Gateway,
    GatewayUnavailableError,
    LLMRequest,
    Message,
    Usage,
    build_gateway,
)
from app.gateway.cache import SemanticCache
from app.gateway.cost import estimate_cost_usd
from app.gateway.providers import DeterministicProvider
from app.gateway.router import Router
from app.gateway.types import LLMResponse, ProviderError
from app.llm import GatewayLLM, analyze_and_validate

CRITICAL_FINDING = {
    "id": "F-001", "ruleId": "formatted-sql-query", "title": "SQL Injection",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "query = '...' + request.args['name']; cursor.execute(query)",
}


def _analysis_req(finding=CRITICAL_FINDING, task="analysis"):
    return LLMRequest(
        messages=[Message(role="system", content="sys"), Message(role="user", content="u")],
        task=task, finding=finding,
    )


# --- cost --------------------------------------------------------------------

def test_cost_estimate_matches_price_table():
    usage = Usage(prompt_tokens=1000, completion_tokens=1000)
    # gpt-4o-mini: 0.00015 + 0.0006 per 1k
    assert estimate_cost_usd("gpt-4o-mini", usage) == round(0.00015 + 0.0006, 6)


def test_deterministic_model_is_free():
    usage = Usage(prompt_tokens=999, completion_tokens=999)
    assert estimate_cost_usd("deterministic", usage) == 0.0


# --- router ------------------------------------------------------------------

def test_router_orders_by_task_with_deterministic_last():
    r = Router()
    assert r.order("analysis")[0] == "openai"
    assert r.order("judge")[0] == "anthropic"
    assert r.order("analysis")[-1] == "deterministic"
    assert r.order("unknown-task")[-1] == "deterministic"


# --- semantic cache ----------------------------------------------------------

def test_cache_exact_and_semantic_hit():
    cache = SemanticCache(similarity=0.8)
    resp = LLMResponse(content="x", provider="p", model="m", usage=Usage(1, 1))
    cache.put("SQL injection in users.py line 42", resp)
    assert cache.get("sql injection in users.py line 42") is resp  # exact (normalized)
    # near match (one extra token) clears the 0.8 Jaccard bar
    assert cache.get("SQL injection in users.py line 42 critical") is resp
    # unrelated prompt misses
    assert cache.get("completely different unrelated text here") is None


# --- providers + gateway core ------------------------------------------------

def test_deterministic_provider_produces_valid_analysis():
    resp = DeterministicProvider().complete(_analysis_req())
    data = json.loads(resp.content)
    assert data["severity"] == "critical"
    assert data["recommendedAction"] == "create_ticket"


def test_gateway_uses_deterministic_offline_and_tracks_metrics():
    gw = build_gateway(Settings())  # no API keys -> deterministic only
    result = gw.complete(_analysis_req())
    assert result.provider == "deterministic"
    assert result.cache_hit is False
    m = gw.metrics()
    assert m["totalRequests"] == 1
    assert m["providers"] == ["deterministic"]


def test_gateway_cache_hit_on_repeat():
    gw = build_gateway(Settings())
    gw.complete(_analysis_req())
    second = gw.complete(_analysis_req())
    assert second.cache_hit is True
    assert second.cost_usd == 0.0
    assert gw.metrics()["cacheHits"] == 1
    assert gw.metrics()["cacheHitRate"] == 0.5


class _FailingProvider:
    name = "openai"
    model = "gpt-4o-mini"

    def is_configured(self):
        return True

    def complete(self, req):
        raise ProviderError("boom")


def test_gateway_falls_back_to_next_provider():
    gw = Gateway([_FailingProvider(), DeterministicProvider()])
    result = gw.complete(_analysis_req())
    assert result.provider == "deterministic"
    assert any(a.provider == "openai" and not a.ok for a in result.attempts)
    assert gw.metrics()["fallbackUsed"] == 1


def test_gateway_raises_when_all_providers_fail():
    gw = Gateway([_FailingProvider()], cache_enabled=False)
    try:
        gw.complete(_analysis_req())
        raise AssertionError("expected GatewayUnavailableError")
    except GatewayUnavailableError:
        assert gw.metrics()["totalFailures"] == 1


def test_reset_clears_cache_and_metrics():
    gw = build_gateway(Settings())
    gw.complete(_analysis_req())
    gw.reset()
    assert gw.metrics()["totalRequests"] == 0
    assert gw.metrics()["cacheSize"] == 0


# --- LLMClient seam wiring ---------------------------------------------------

def test_gateway_llm_returns_valid_json_for_node():
    client = GatewayLLM(build_gateway(Settings()))
    result, attempts, error = analyze_and_validate(CRITICAL_FINDING, client, max_retries=2)
    assert error is None
    assert attempts == 1
    assert result.recommendedAction.value == "create_ticket"
