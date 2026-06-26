"""AI Gateway — the single LLM egress (ported from ai-secops-copilot, ADR-014).

One seam owns routing, semantic caching, ordered fallback, and cost/latency/token
tracking, so the rest of the kernel stays provider-agnostic and offline-deterministic.
The deterministic provider is always the final fallback (no keys, $0), so ``complete()``
never hard-fails offline.
"""

from __future__ import annotations

from .gateway import Gateway
from .providers import (
    AnthropicProvider,
    DeterministicProvider,
    GeminiProvider,
    OpenAIProvider,
)
from .router import Router
from .types import (
    GatewayResult,
    GatewayUnavailableError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderError,
    Usage,
)

__all__ = [
    "Gateway",
    "Router",
    "DeterministicProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "Usage",
    "GatewayResult",
    "LLMProvider",
    "ProviderError",
    "GatewayUnavailableError",
]
