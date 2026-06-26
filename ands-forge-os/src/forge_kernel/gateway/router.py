"""Task-aware provider routing (ported, ADR-014).

Different tasks want different cost/quality trade-offs:

* ``draft``  — high-volume artifact generation: prefer the cheap, fast model first.
* ``judge``  — reasoning-quality scoring (Critic / red-team): prefer the stronger model.

The router returns an *ordered* list of provider names; the Gateway tries them in order
(fallback) and always appends ``deterministic`` last so an offline or fully-degraded
runtime still returns a valid answer. Unknown tasks fall back to the draft order.
"""

from __future__ import annotations

_ROUTES: dict[str, list[str]] = {
    "draft": ["gemini", "openai", "anthropic"],
    "judge": ["gemini", "anthropic", "openai"],
}

_FALLBACK = "deterministic"


class Router:
    def __init__(self, routes: dict[str, list[str]] | None = None) -> None:
        self._routes = routes or _ROUTES

    def order(self, task: str) -> list[str]:
        preferred = self._routes.get(task, self._routes["draft"])
        order = list(preferred)
        if _FALLBACK not in order:
            order.append(_FALLBACK)  # ultimate fallback: never hard-fail
        return order
