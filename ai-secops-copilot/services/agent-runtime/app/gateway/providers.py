"""LLM providers behind the Gateway (Day 11, ADR-014).

* ``DeterministicProvider`` — offline, always configured, no API keys. Computes the
  analysis from the structured finding via ``analysis.analyze_finding`` and returns the
  exact JSON a well-behaved model would emit. This is the reproducible default and the
  Gateway's ultimate fallback, so the runtime never hard-fails on a provider outage.
* ``OpenAIProvider`` / ``AnthropicProvider`` — real egress, configured only when their API
  key is set. ``httpx`` is imported lazily inside ``complete()`` so importing this module
  needs no third-party packages.
"""

from __future__ import annotations

import json

from .. import analysis as analysis_core
from .types import LLMRequest, LLMResponse, ProviderError, Usage


def _estimate_tokens(text: str) -> int:
    """~4 chars/token, the common rough estimate for budgeting (not billing)."""
    return max(1, len(text) // 4)


class DeterministicProvider:
    """Offline, reproducible stand-in. Always available; analysis-only."""

    name = "deterministic"
    model = "deterministic"

    def is_configured(self) -> bool:
        return True

    def complete(self, req: LLMRequest) -> LLMResponse:
        if req.finding is None:
            raise ProviderError("deterministic provider requires a structured finding")
        content = json.dumps(analysis_core.analyze_finding(req.finding))
        usage = Usage(
            prompt_tokens=_estimate_tokens("".join(m.content for m in req.messages)),
            completion_tokens=_estimate_tokens(content),
        )
        return LLMResponse(content=content, provider=self.name, model=self.model, usage=usage)


class OpenAIProvider:
    """OpenAI Chat Completions with JSON-object response format (ADR-010)."""

    name = "openai"

    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_s: float) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, req: LLMRequest) -> LLMResponse:
        import httpx

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content, provider=self.name, model=self.model,
                usage=Usage(
                    prompt_tokens=int(usage.get("prompt_tokens", _estimate_tokens(content))),
                    completion_tokens=int(
                        usage.get("completion_tokens", _estimate_tokens(content))
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - normalize to ProviderError for fallback
            raise ProviderError(f"openai: {exc}") from exc


class AnthropicProvider:
    """Anthropic Messages API. System prompt is a top-level field, not a message."""

    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_s: float) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, req: LLMRequest) -> LLMResponse:
        import httpx

        system = "\n\n".join(m.content for m in req.messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content}
            for m in req.messages
            if m.role in ("user", "assistant")
        ]
        payload = {
            "model": self.model,
            "system": system,
            "messages": turns,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        try:
            resp = httpx.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self._timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            content = "".join(
                block.get("text", "") for block in data.get("content", [])
                if block.get("type") == "text"
            )
            usage = data.get("usage", {})
            return LLMResponse(
                content=content, provider=self.name, model=self.model,
                usage=Usage(
                    prompt_tokens=int(usage.get("input_tokens", _estimate_tokens(content))),
                    completion_tokens=int(usage.get("output_tokens", _estimate_tokens(content))),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - normalize to ProviderError for fallback
            raise ProviderError(f"anthropic: {exc}") from exc
