"""Shared contracts for the AI Gateway egress (Day 11, ADR-014).

Stdlib-only so the gateway imports without third-party packages (the eval harness and
the deterministic offline path both load it). Real providers import ``httpx`` lazily,
inside ``complete()`` — never at module import.

These mirror the NestJS gateway's ``llm.types.ts`` so the Python egress and the Node
control-plane scaffold describe the same contract.
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

    ``finding`` is an optional structured payload the offline ``DeterministicProvider``
    uses to compute the analysis without a model; real providers ignore it and use
    ``messages``. ``task`` drives routing (e.g. "analysis" vs "judge").
    """

    messages: Sequence[Message]
    task: str = "analysis"
    temperature: float = 0.0
    max_tokens: int = 512
    finding: Mapping[str, object] | None = None


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
