"""Approximate LLM cost estimation for observability (ported, ADR-014).

Public list prices in USD per 1K tokens — estimates for the cost dashboard, not billing.
The offline ``deterministic`` model is free, so cost stays $0 in the no-keys default.
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
    # Simulated "live" model for the no-keys demo: priced like a cheap real model so the
    # cost dashboard shows realistic, non-zero spend.
    "fake-live-1": _Price(0.00015, 0.0006),
    "gpt-4o-mini": _Price(0.00015, 0.0006),
    "gpt-4o": _Price(0.005, 0.015),
    "claude-3-5-sonnet-latest": _Price(0.003, 0.015),
    "claude-3-5-haiku-latest": _Price(0.0008, 0.004),
    # Gemini — approximate public list prices (free tier bills $0; these are dashboard
    # estimates only). Flash = cheap drafting tier, Pro = strong reasoning tier.
    "gemini-2.5-flash": _Price(0.000075, 0.0003),
    "gemini-2.0-flash": _Price(0.000075, 0.0003),
    "gemini-2.5-pro": _Price(0.00125, 0.005),
    # Groq (OpenAI-compatible). Free tier bills $0; these mirror Groq's low list prices.
    "llama-3.3-70b-versatile": _Price(0.00059, 0.00079),
    "llama-3.1-8b-instant": _Price(0.00005, 0.00008),
}

_DEFAULT_PRICE = _Price(0.001, 0.002)


def estimate_cost_usd(model: str, usage: Usage) -> float:
    price = _PRICE_TABLE.get(model, _DEFAULT_PRICE)
    cost = (
        (usage.prompt_tokens / 1000) * price.input_per_1k
        + (usage.completion_tokens / 1000) * price.output_per_1k
    )
    return round(cost, 6)
