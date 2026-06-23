"""The LLM client seam + structured-output validation (ADR-006, ADR-010).

The Finding Analysis Node never talks to a model provider directly. It talks to an
``LLMClient`` whose only job is: given a finding, return a *raw* JSON string (what a
model would emit). The node then parses + validates that string against
``schemas.AnalysisResult`` before anything acts on it, re-prompting a bounded number
of times on invalid output and escalating if it still fails.

Two implementations:
  * ``DeterministicLLM`` (Day 2): produces the structured analysis offline via
    ``analysis.analyze_finding``. No API keys, fully reproducible.
  * ``GatewayLLM`` (Day 11): routes the analysis prompt through the in-process AI Gateway
    (``app.gateway``) — the single egress that does provider routing, ordered fallback
    (OpenAI -> Claude -> deterministic), a semantic cache, and cost/latency tracking. With
    no API keys it resolves to the deterministic provider, so behaviour is identical to
    ``DeterministicLLM`` while the gateway still records cache/cost/latency metrics.

``get_default_client()`` returns the GatewayLLM, so every analysis flows through the one
egress; the deterministic fallback keeps the offline path reproducible.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from pydantic import ValidationError

from . import analysis as analysis_core
from .config import Settings, get_settings
from .prompts import build_analysis_messages
from .schemas import AnalysisResult

Finding = Mapping[str, object]


class LLMClient(Protocol):
    """A provider-agnostic analysis client: finding in, raw JSON completion out."""

    name: str

    def analyze(self, finding: Finding) -> str:  # pragma: no cover - protocol
        ...


class DeterministicLLM:
    """Offline, reproducible stand-in for the LLM (Day 2 default).

    Mirrors what a well-behaved model returns: a single JSON object conforming to
    the structured-output contract. The reasoning lives in ``analysis.py``.
    """

    name = "deterministic"

    def analyze(self, finding: Finding) -> str:
        result = analysis_core.analyze_finding(finding)
        return json.dumps(result)


class GatewayLLM:
    """Analysis via the in-process AI Gateway (Day 11, ADR-014).

    Builds the injection-hardened prompt (``prompts.build_analysis_messages``) and sends it
    through the Gateway, which routes/falls back across providers and tracks cost + latency.
    The structured finding rides along so the offline deterministic provider can answer with
    no model call. Returns the raw JSON completion; the node validates it (ADR-010).
    """

    name = "gateway"

    def __init__(self, gateway, *, context: str | None = None) -> None:
        self._gateway = gateway
        self._context = context

    def analyze(self, finding: Finding) -> str:
        # Imported here to avoid a circular import (gateway imports config; llm too).
        from .gateway import LLMRequest, Message

        system, user = build_analysis_messages(finding, self._context)
        req = LLMRequest(
            messages=[Message(role="system", content=system), Message(role="user", content=user)],
            task="analysis",
            finding=finding,
        )
        return self._gateway.complete(req).response.content


def get_default_client(settings: Settings | None = None) -> LLMClient:
    """The runtime's analysis client: the AI Gateway egress (deterministic fallback)."""
    from .gateway import get_gateway

    settings = settings or get_settings()
    return GatewayLLM(get_gateway(settings))


def analyze_and_validate(
    finding: Finding,
    client: LLMClient,
    *,
    max_retries: int = 2,
) -> tuple[AnalysisResult | None, int, str | None]:
    """Call the client and validate its output, re-prompting on invalid JSON/schema.

    Returns ``(result, attempts, error)``. ``result`` is ``None`` when every attempt
    produced invalid output; the caller then escalates (PRODUCT_VISION failure table).
    Bounded retries cap the cost of a misbehaving model.
    """
    last_error: str | None = None
    attempts = 0
    for attempt in range(1, max_retries + 1):
        attempts = attempt
        raw = client.analyze(finding)
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            last_error = f"invalid JSON from model: {exc}"
            continue
        try:
            return AnalysisResult.model_validate(data), attempts, None
        except ValidationError as exc:
            last_error = f"schema validation failed: {exc.error_count()} error(s)"
            continue
    return None, attempts, last_error
