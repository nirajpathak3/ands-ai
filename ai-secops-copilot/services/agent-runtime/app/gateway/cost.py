"""Approximate LLM cost estimation for observability (ADR-014).

Public list prices in USD per 1K tokens — configurable estimates for the cost dashboard,
not billing. Mirrors the NestJS gateway's ``cost.ts``. The offline ``deterministic`` model
is free (it runs no paid call), so cost stays $0 in the no-keys default.
"""

from __future__ import annotations

from .types import Usage


class _Price:
    __slots__ = ("input_per_1k", "output_per_1k")

    def __init__(self, input_per_1k: float, output_per_1k: float) -> None:
        self.input_per_1k = input_per_1k
        self.output_per_1k = output_per_1k


_PRICE_TABLE: dict[str, _Price] = {
    "deterministic": _Price(0.0, 0.0),
    "gpt-4o-mini": _Price(0.00015, 0.0006),
    "gpt-4o": _Price(0.005, 0.015),
    "claude-3-5-sonnet-latest": _Price(0.003, 0.015),
    "claude-3-5-haiku-latest": _Price(0.0008, 0.004),
}

_DEFAULT_PRICE = _Price(0.001, 0.002)


def estimate_cost_usd(model: str, usage: Usage) -> float:
    price = _PRICE_TABLE.get(model, _DEFAULT_PRICE)
    cost = (
        (usage.prompt_tokens / 1000) * price.input_per_1k
        + (usage.completion_tokens / 1000) * price.output_per_1k
    )
    return round(cost, 6)
