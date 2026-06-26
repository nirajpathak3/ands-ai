"""Shared contracts for the AI Gateway egress (ported, ADR-014).

Stdlib-only so the gateway imports without third-party packages. Real providers import
``httpx`` lazily, inside ``complete()`` — never at module import — so the offline kernel
needs nothing installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

Role = str  # "system" | "user" | "assistant"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """A model-agnostic completion request.

    ``task`` drives routing (e.g. "draft" vs "judge"). ``payload`` is an optional
    structured input the deterministic offline provider uses to compute a reproducible
    response without a model; real providers ignore it and use ``messages``.

    ``cache`` selects the cache policy. Free-text generation can reuse a *near-identical*
    prompt ("fuzzy", the default, ADR-014). **Structured** generation must NOT: two prompts
    that differ only in a few required keys are >0.92 similar yet need different outputs, so
    a fuzzy hit would return another artifact's content. Such callers pass "exact" (reuse
    only an identical prompt) or "off".
    """

    messages: Sequence[Message]
    task: str = "draft"
    temperature: float = 0.0
    max_tokens: int = 1024
    payload: Mapping[str, object] | None = None
    cache: str = "fuzzy"  # "fuzzy" | "exact" | "off"
    # Optional per-call model override (the model tier resolved for this task/stage). When
    # None, a provider uses its own configured default. Deterministic providers ignore it.
    model: str | None = None
    # Ask the provider to enforce a JSON-object response (OpenAI/Gemini response_format).
    json_mode: bool = False


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: Usage


@dataclass
class Attempt:
    provider: str
    ok: bool
    error: str | None = None


@dataclass
class GatewayResult:
    """What the Gateway returns to callers, enriched with observability data."""

    response: LLMResponse
    provider: str
    model: str
    latency_ms: float
    cost_usd: float
    cache_hit: bool
    attempts: list[Attempt] = field(default_factory=list)


@runtime_checkable
class LLMProvider(Protocol):
    """One model provider behind the Gateway."""

    name: str
    model: str

    def is_configured(self) -> bool:  # pragma: no cover - protocol
        ...

    def complete(self, req: LLMRequest) -> LLMResponse:  # pragma: no cover - protocol
        ...


class ProviderError(RuntimeError):
    """A provider failed (network/auth/parse). Triggers fallback to the next provider."""


class GatewayUnavailableError(RuntimeError):
    """Every routed provider failed. Offline this never happens (deterministic fallback)."""
