"""AI Gateway package: the single LLM egress (Day 11, ADR-006 / ADR-014).

``get_gateway(settings)`` builds (and memoizes) a process-wide Gateway from settings:
real OpenAI/Anthropic providers when their API keys are present, with the always-on
deterministic provider as the final fallback. A single instance is shared so cost,
cache, and latency metrics accumulate across requests; ``reset_gateway()`` rebuilds it
(used by the demo reset and tests).
"""

from __future__ import annotations

from ..config import Settings
from .cache import SemanticCache
from .gateway import Gateway
from .providers import AnthropicProvider, DeterministicProvider, OpenAIProvider
from .router import Router
from .types import (
    GatewayResult,
    GatewayUnavailableError,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderError,
    Usage,
)

__all__ = [
    "Gateway",
    "GatewayResult",
    "GatewayUnavailableError",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "ProviderError",
    "Usage",
    "build_gateway",
    "get_gateway",
    "reset_gateway",
]


def build_gateway(settings: Settings) -> Gateway:
    """Construct a fresh Gateway from settings (no memoization)."""
    providers = [
        OpenAIProvider(
            api_key=settings.openai_api_key, model=settings.openai_model,
            base_url=settings.openai_base_url, timeout_s=settings.llm_timeout_s,
        ),
        AnthropicProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model,
            base_url=settings.anthropic_base_url, timeout_s=settings.llm_timeout_s,
        ),
        DeterministicProvider(),
    ]
    return Gateway(
        providers,
        router=Router(),
        cache=SemanticCache(similarity=settings.llm_cache_similarity),
        cache_enabled=settings.llm_cache_enabled,
    )


_GATEWAY: Gateway | None = None


def get_gateway(settings: Settings) -> Gateway:
    """Return the shared Gateway, building it on first use."""
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = build_gateway(settings)
    return _GATEWAY


def reset_gateway(settings: Settings | None = None) -> Gateway | None:
    """Rebuild the shared Gateway (drops cache + metrics). Returns the new instance."""
    global _GATEWAY
    _GATEWAY = build_gateway(settings) if settings is not None else None
    return _GATEWAY
