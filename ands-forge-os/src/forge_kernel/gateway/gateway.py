"""The AI Gateway: the single LLM egress (ported, ADR-014).

One place owns routing, semantic caching, ordered fallback, and cost/latency/token
tracking. ``complete()`` is the only entry point:

    route (by task) -> cache lookup -> try providers in order -> record metrics -> cache

The deterministic provider is always the final fallback, so offline (no API keys) this
never raises: it returns a reproducible response at $0 cost.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from contextlib import nullcontext

from .cache import SemanticCache
from .cost import estimate_cost_usd
from .router import Router
from .types import (
    Attempt,
    GatewayResult,
    GatewayUnavailableError,
    LLMProvider,
    LLMRequest,
)


class Gateway:
    def __init__(
        self,
        providers: Sequence[LLMProvider],
        *,
        router: Router | None = None,
        cache: SemanticCache | None = None,
        cache_enabled: bool = True,
        observer: Callable[[dict], None] | None = None,
        tracer=None,
    ) -> None:
        self._providers = {p.name: p for p in providers}
        self._router = router or Router()
        self._cache = cache if cache is not None else SemanticCache()
        self._cache_enabled = cache_enabled
        self._observer = observer
        self._tracer = tracer
        self._metrics = _new_metrics()

    # --- core -----------------------------------------------------------------

    def complete(self, req: LLMRequest) -> GatewayResult:
        span_cm = (
            self._tracer.start_span("llm.complete", task=req.task)
            if self._tracer is not None else nullcontext()
        )
        with span_cm as span:
            result = self._complete(req)
            if span is not None:
                span.attributes.update({
                    "provider": result.provider, "model": result.model,
                    "cacheHit": result.cache_hit, "costUsd": result.cost_usd,
                })
            self._notify(result, req.task)
            return result

    def _complete(self, req: LLMRequest) -> GatewayResult:
        self._metrics["totalRequests"] += 1
        start = time.perf_counter()

        cache_key = self._cache_key(req)
        use_cache = self._cache_enabled and req.cache != "off"
        if use_cache and cache_key is not None:
            cached = self._cache.get(cache_key, fuzzy=req.cache == "fuzzy")
            if cached is not None:
                self._metrics["cacheHits"] += 1
                latency_ms = (time.perf_counter() - start) * 1000
                return GatewayResult(
                    response=cached, provider=cached.provider, model=cached.model,
                    latency_ms=round(latency_ms, 3), cost_usd=0.0, cache_hit=True,
                    attempts=[Attempt(provider=cached.provider, ok=True)],
                )

        attempts: list[Attempt] = []
        for name in self._router.order(req.task):
            provider = self._providers.get(name)
            if provider is None or not provider.is_configured():
                attempts.append(Attempt(provider=name, ok=False, error="not_configured"))
                continue
            try:
                response = provider.complete(req)
            except Exception as exc:  # noqa: BLE001 - any failure -> try next provider
                attempts.append(Attempt(provider=name, ok=False, error=str(exc)))
                continue

            latency_ms = (time.perf_counter() - start) * 1000
            cost_usd = estimate_cost_usd(response.model, response.usage)
            attempts.append(Attempt(provider=name, ok=True))
            # A provider skipped as "not_configured" (e.g. no API key offline) is not a
            # degradation, so it must not inflate the fallback rate.
            real_failures = sum(
                1 for a in attempts if not a.ok and a.error != "not_configured"
            )
            if real_failures > 0:
                self._metrics["fallbackUsed"] += 1
            self._record(name, latency_ms, cost_usd, response.usage.total_tokens)
            if use_cache and cache_key is not None:
                self._cache.put(cache_key, response)
            return GatewayResult(
                response=response, provider=name, model=response.model,
                latency_ms=round(latency_ms, 3), cost_usd=cost_usd, cache_hit=False,
                attempts=attempts,
            )

        self._metrics["totalFailures"] += 1
        raise GatewayUnavailableError(
            "all routed providers failed: "
            + ", ".join(f"{a.provider}={a.error}" for a in attempts)
        )

    def _notify(self, result: GatewayResult, task: str) -> None:
        if self._observer is None:
            return
        try:
            self._observer({
                "latency_ms": result.latency_ms, "cost_usd": result.cost_usd,
                "provider": result.provider, "cache_hit": result.cache_hit,
                "tokens": result.response.usage.total_tokens, "task": task,
            })
        except Exception:  # noqa: BLE001 - observability must never break egress
            pass

    # --- observability --------------------------------------------------------

    def metrics(self) -> dict:
        m = self._metrics
        n = m["totalRequests"] or 1
        served = (m["totalRequests"] - m["cacheHits"]) or 1
        return {
            **{k: v for k, v in m.items() if k != "byProvider"},
            "byProvider": dict(m["byProvider"]),
            "cacheHitRate": round(m["cacheHits"] / n, 4),
            "fallbackRate": round(m["fallbackUsed"] / served, 4),
            "meanLatencyMs": round(m["totalLatencyMs"] / served, 3),
            "costPerRequestUsd": round(m["totalCostUsd"] / served, 6),
            "cacheSize": len(self._cache),
            "providers": sorted(
                name for name, p in self._providers.items() if p.is_configured()
            ),
        }

    def reset(self) -> None:
        self._metrics = _new_metrics()
        self._cache.clear()

    # --- internals ------------------------------------------------------------

    def _cache_key(self, req: LLMRequest) -> str | None:
        if not req.messages:
            return None
        prefix = f"{req.task}|{req.model or ''}\n"
        return prefix + "\n".join(f"{m.role}:{m.content}" for m in req.messages)

    def _record(self, provider: str, latency_ms: float, cost_usd: float, tokens: int) -> None:
        m = self._metrics
        m["totalLatencyMs"] += latency_ms
        m["totalCostUsd"] = round(m["totalCostUsd"] + cost_usd, 6)
        m["totalTokens"] += tokens
        m["byProvider"][provider] = m["byProvider"].get(provider, 0) + 1


def _new_metrics() -> dict:
    return {
        "totalRequests": 0,
        "totalFailures": 0,
        "fallbackUsed": 0,
        "cacheHits": 0,
        "totalCostUsd": 0.0,
        "totalTokens": 0,
        "totalLatencyMs": 0.0,
        "byProvider": {},
    }
