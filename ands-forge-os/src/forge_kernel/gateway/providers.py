"""LLM providers behind the Gateway (ported + generalized, ADR-014).

* ``DeterministicProvider`` — offline, always configured, no API keys. Domain-agnostic:
  it returns a reproducible response derived from the request (an explicit
  ``payload["response"]`` if the caller supplied one, otherwise a deterministic,
  content-hashed echo of the task). This is the kernel's ultimate fallback, so the
  runtime never hard-fails on a provider outage and offline runs cost $0.
* ``OpenAIProvider`` / ``AnthropicProvider`` — real egress, configured only when their
  API key is set. ``httpx`` is imported lazily inside ``complete()``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re

from .types import LLMRequest, LLMResponse, ProviderError, Usage


def _estimate_tokens(text: str) -> int:
    """~4 chars/token, the common rough estimate for budgeting (not billing)."""
    return max(1, len(text) // 4)


def _select_model(req_model: str | None, default: str, family: str) -> str:
    """Honor a per-request model only if it belongs to this provider's family.

    The resolved model tier (e.g. ``gemini-2.5-flash``) is provider-specific. When the
    gateway falls back across providers (Gemini 429 -> Groq/OpenAI), a foreign id would
    400/404, so each provider ignores a model id from another family and uses its own
    configured default instead. ``family`` is one of "gemini", "anthropic", "openai"
    (OpenAI-compatible, including Groq/OpenRouter/etc.).
    """
    if not req_model:
        return default
    if family == "gemini":
        return req_model if "gemini" in req_model else default
    if family == "anthropic":
        return req_model if "claude" in req_model else default
    # OpenAI-compatible: accept anything that isn't clearly another family's id.
    if "gemini" in req_model or "claude" in req_model:
        return default
    return req_model


class DeterministicProvider:
    """Offline, reproducible stand-in. Always available; no network, $0."""

    name = "deterministic"
    model = "deterministic"

    def is_configured(self) -> bool:
        return True

    def complete(self, req: LLMRequest) -> LLMResponse:
        if req.payload is not None and "seed" in req.payload:
            # An agent supplied a reproducible structured artifact to echo (offline path).
            content = json.dumps(req.payload["seed"])
        elif req.payload is not None and "response" in req.payload:
            content = str(req.payload["response"])
        else:
            prompt = "\n".join(f"{m.role}:{m.content}" for m in req.messages)
            digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
            content = json.dumps(
                {"task": req.task, "deterministic": True, "promptDigest": digest}
            )
        usage = Usage(
            prompt_tokens=_estimate_tokens("".join(m.content for m in req.messages)),
            completion_tokens=_estimate_tokens(content),
        )
        return LLMResponse(content=content, provider=self.name, model=self.model, usage=usage)


_KEYS_RE = re.compile(r"keys:\s*(\[[^\]]*\])")
_TITLE_RE = re.compile(r"Produce the '([^']+)' artifact")
_VISION_RE = re.compile(r"<vision>\s*(.*?)\s*</vision>", re.DOTALL)


class FakeLiveProvider:
    """A scripted stand-in for a real LLM — for demoing/testing the *live* path with no keys.

    Unlike ``DeterministicProvider`` (which echoes a caller-supplied seed), this provider
    behaves like a real model: it reads the structured-output contract from the prompt and
    *generates* prose-style JSON for exactly those keys, so the agent's parse + validate +
    reprompt logic (ADR-010) and the LLM-as-judge seam are exercised end-to-end — yet it is
    fully deterministic, so demos and CI stay reproducible and cost is simulated (non-zero).

    With ``flaky=True`` it returns one invalid (non-JSON) response per artifact before a
    valid one, to make the **bounded reprompt** visible in a demo.
    """

    name = "fake-live"
    model = "fake-live-1"

    # The agent's reprompt nudge contains this phrase; we key flakiness off it so the
    # behavior is stateless + deterministic (robust to the gateway cache and stage re-runs).
    _REPROMPT_MARK = "previous response was invalid"

    def __init__(self, *, flaky: bool = False) -> None:
        self._flaky = flaky

    def is_configured(self) -> bool:
        return True

    def complete(self, req: LLMRequest) -> LLMResponse:
        text = "\n".join(m.content for m in req.messages)
        if req.task == "judge":
            return self._respond(req, json.dumps({
                "score": 0.86,
                "findings": [
                    "Clarify the rollback / failure path for the primary flow.",
                    "Enumerate abuse/misuse cases and an explicit non-goal.",
                ],
            }))
        if self._flaky and self._REPROMPT_MARK not in text:
            # First attempt (no reprompt yet): return non-JSON so the agent reprompts once.
            title = self._match(_TITLE_RE, text) or "artifact"
            return self._respond(req, f"Sure — drafting the {title} now. (pending)")
        keys = self._parse_keys(text)
        # Read the vision only from user turns (the system contract mentions "<vision>" too).
        user_text = "\n".join(m.content for m in req.messages if m.role == "user")
        vision = self._match(_VISION_RE, user_text) or "the product"
        obj = {k: self._value_for(k, vision) for k in keys}
        return self._respond(req, json.dumps(obj))

    # --- helpers --------------------------------------------------------------

    @staticmethod
    def _match(pattern: re.Pattern[str], text: str) -> str | None:
        m = pattern.search(text)
        return m.group(1).strip() if m else None

    def _parse_keys(self, text: str) -> list[str]:
        m = _KEYS_RE.search(text)
        if m:
            try:
                parsed = ast.literal_eval(m.group(1))
                if isinstance(parsed, list) and parsed:
                    return [str(k) for k in parsed]
            except (ValueError, SyntaxError):
                pass
        return ["summary"]

    @staticmethod
    def _value_for(key: str, vision: str) -> str:
        product = " ".join(vision.split()[:10]) or "the product"
        pretty = key.replace("_", " ")
        return (
            f"{pretty.capitalize()} for '{product}': a concrete, testable commitment "
            f"derived from the vision, scoped to the MVP and traceable to user value."
        )

    def _respond(self, req: LLMRequest, content: str) -> LLMResponse:
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
        return _openai_chat_complete(
            self.name, _select_model(req.model, self.model, "openai"), self._base_url,
            self._api_key, self._timeout_s, req,
        )


def _openai_chat_complete(
    provider: str, model: str, base_url: str, api_key: str, timeout_s: float, req: LLMRequest
) -> LLMResponse:
    """Shared OpenAI-compatible Chat Completions call (OpenAI + Gemini's OpenAI surface)."""
    import httpx

    payload: dict = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in req.messages],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    if req.json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content, provider=provider, model=model,
            usage=Usage(
                prompt_tokens=int(usage.get("prompt_tokens", _estimate_tokens(content))),
                completion_tokens=int(usage.get("completion_tokens", _estimate_tokens(content))),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - normalize to ProviderError for fallback
        raise ProviderError(f"{provider}: {exc}") from exc


class GeminiProvider:
    """Google Gemini via its OpenAI-compatible REST surface (free-tier friendly).

    Uses a per-request model when one is supplied (the resolved tier), else the configured
    default — so the same provider serves both the cheap drafting tier and the strong
    reasoning tier. JSON mode is honored through ``response_format``.
    """

    name = "gemini"

    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_s: float) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def complete(self, req: LLMRequest) -> LLMResponse:
        return _openai_chat_complete(
            self.name, _select_model(req.model, self.model, "gemini"), self._base_url,
            self._api_key, self._timeout_s, req,
        )


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
        model = _select_model(req.model, self.model, "anthropic")
        payload = {
            "model": model,
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
                content=content, provider=self.name, model=model,
                usage=Usage(
                    prompt_tokens=int(usage.get("input_tokens", _estimate_tokens(content))),
                    completion_tokens=int(usage.get("output_tokens", _estimate_tokens(content))),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - normalize to ProviderError for fallback
            raise ProviderError(f"anthropic: {exc}") from exc
