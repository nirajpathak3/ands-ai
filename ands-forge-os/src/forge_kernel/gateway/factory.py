"""Build the AI Gateway provider chain from settings (offline-first).

Always includes the deterministic provider (the ultimate fallback). Real providers are
added ONLY in live mode and only when their API key is configured — so offline stays fully
deterministic and $0 even if keys happen to be present in the environment.
"""

from __future__ import annotations

from ..config import Settings
from .gateway import Gateway
from .providers import (
    AnthropicProvider,
    DeterministicProvider,
    FakeLiveProvider,
    GeminiProvider,
    OpenAIProvider,
)
from .router import Router
from .types import LLMProvider


def build_gateway(settings: Settings, *, tracer=None, observer=None) -> Gateway:
    providers: list[LLMProvider] = []
    router: Router | None = None
    if not settings.offline:
        # Live-only: a scripted provider that simulates a real model so the live path can be
        # demoed/tested with no API keys. Routed first so it wins over (unconfigured) reals.
        if settings.fake_live:
            providers.append(FakeLiveProvider(flaky=settings.fake_live_flaky))
            router = Router({
                "draft": ["fake-live", "gemini", "openai", "anthropic"],
                "judge": ["fake-live", "gemini", "anthropic", "openai"],
            })
        if settings.gemini_api_key:
            providers.append(
                GeminiProvider(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                    base_url=settings.gemini_base_url,
                    timeout_s=settings.llm_timeout_s,
                )
            )
        if settings.openai_api_key:
            providers.append(
                OpenAIProvider(
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    base_url=settings.openai_base_url,
                    timeout_s=settings.llm_timeout_s,
                )
            )
        if settings.anthropic_api_key:
            providers.append(
                AnthropicProvider(
                    api_key=settings.anthropic_api_key,
                    model=settings.anthropic_model,
                    base_url=settings.anthropic_base_url,
                    timeout_s=settings.llm_timeout_s,
                )
            )
    providers.append(DeterministicProvider())  # always-on final fallback
    return Gateway(
        providers,
        router=router,
        cache_enabled=settings.llm_cache_enabled,
        tracer=tracer,
        observer=observer,
    )
