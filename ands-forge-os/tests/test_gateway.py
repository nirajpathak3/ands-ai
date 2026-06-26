"""AI Gateway: offline determinism, $0 cost, ordered fallback, cache."""

from __future__ import annotations

from forge_kernel.config import get_settings
from forge_kernel.gateway import Gateway, LLMRequest, Message, ProviderError
from forge_kernel.gateway.factory import build_gateway
from forge_kernel.gateway.providers import DeterministicProvider


def _req(text: str = "draft a PRD") -> LLMRequest:
    return LLMRequest(messages=[Message("system", "you are an agent"), Message("user", text)])


def test_offline_uses_deterministic_provider_at_zero_cost():
    gw = build_gateway(get_settings())
    result = gw.complete(_req())
    assert result.provider == "deterministic"
    assert result.cost_usd == 0.0
    assert gw.metrics()["providers"] == ["deterministic"]


def test_deterministic_provider_is_reproducible():
    gw = build_gateway(get_settings())
    a = gw.complete(_req("identical prompt"))
    gw.reset()
    b = gw.complete(_req("identical prompt"))
    assert a.response.content == b.response.content


def test_cache_hit_on_repeat_prompt():
    gw = build_gateway(get_settings())
    gw.complete(_req("same prompt please"))
    second = gw.complete(_req("same prompt please"))
    assert second.cache_hit is True
    assert gw.metrics()["cacheHits"] == 1


def test_payload_response_is_echoed():
    gw = build_gateway(get_settings())
    req = LLMRequest(messages=[Message("user", "x")], payload={"response": "HELLO"})
    assert gw.complete(req).response.content == "HELLO"


class _Boom:
    name = "openai"
    model = "gpt-4o-mini"

    def is_configured(self):
        return True

    def complete(self, req):
        raise ProviderError("simulated outage")


def test_fallback_to_deterministic_when_real_provider_fails():
    gw = Gateway([_Boom(), DeterministicProvider()])
    result = gw.complete(_req())
    assert result.provider == "deterministic"
    assert gw.metrics()["fallbackUsed"] == 1
