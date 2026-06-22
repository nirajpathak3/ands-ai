"""The LLM client seam + structured-output validation (ADR-006, ADR-010).

The Finding Analysis Node never talks to a model provider directly. It talks to an
``LLMClient`` whose only job is: given a finding, return a *raw* JSON string (what a
model would emit). The node then parses + validates that string against
``schemas.AnalysisResult`` before anything acts on it, re-prompting a bounded number
of times on invalid output and escalating if it still fails.

Two implementations:
  * ``DeterministicLLM`` (default, Day 2): produces the structured analysis offline
    via ``analysis.analyze_finding``. No API keys, fully reproducible — the walking
    skeleton and CI run with this.
  * ``GatewayLLM`` (Day 11 stub): will POST the prompt to the NestJS AI Gateway
    (single egress -> OpenAI, Claude fallback, semantic cache, cost/latency). Wired
    later; the seam exists now so swapping it in changes nothing downstream.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from pydantic import ValidationError

from . import analysis as analysis_core
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
    """Real LLM via the NestJS AI Gateway. Wired on Day 11 (stub for now)."""

    name = "gateway"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def analyze(self, finding: Finding) -> str:
        _system, _user = build_analysis_messages(finding)
        raise NotImplementedError(
            "GatewayLLM is wired on Day 11. Until then the runtime uses DeterministicLLM. "
            "It will POST the analysis prompt to the AI Gateway (OpenAI + Claude fallback)."
        )


def get_default_client() -> LLMClient:
    """The client the runtime uses today: the offline deterministic analyzer."""
    return DeterministicLLM()


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
