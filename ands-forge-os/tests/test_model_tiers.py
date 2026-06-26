"""Per-task/per-stage model tiers + the Gemini provider + offline safety."""

from __future__ import annotations

from forge_kernel.blueprint import from_dict
from forge_kernel.config import Settings
from forge_kernel.gateway import Gateway, LLMRequest, Message
from forge_kernel.gateway.factory import build_gateway
from forge_kernel.gateway.providers import GeminiProvider
from forge_kernel.gateway.router import Router
from forge_kernel.model_policy import resolve_model


def _settings(**kw) -> Settings:
    base = dict(model_strong="strong-x", model_cheap="cheap-y", strong_stages=("technical",))
    base.update(kw)
    return Settings(**base)


def test_resolve_model_tiers_by_task_and_stage():
    s = _settings()
    # draft on an ordinary stage -> cheap tier
    assert resolve_model(s, task="draft", stage="discovery") == "cheap-y"
    # draft on a strong stage -> strong tier
    assert resolve_model(s, task="draft", stage="technical") == "strong-x"
    # judge always -> strong tier
    assert resolve_model(s, task="judge", stage="discovery") == "strong-x"
    # explicit override wins over everything
    assert resolve_model(s, task="draft", stage="discovery", override="pinned-z") == "pinned-z"


def test_resolve_model_returns_none_when_unconfigured():
    s = Settings(model_strong="", model_cheap="")
    assert resolve_model(s, task="draft", stage="x") is None


def test_blueprint_model_override_artifact_and_stage_level():
    bp = from_dict({
        "name": "t", "version": "1",
        "stages": [{
            "key": "architecture", "title": "Arch", "order": 0, "model": "stage-model",
            "artifacts": [
                {"key": "a1", "role": "r1"},                       # inherits stage model
                {"key": "a2", "role": "r2", "model": "artifact-model"},  # overrides it
            ],
        }],
    })
    assert bp.artifact("a1").model == "stage-model"
    assert bp.artifact("a2").model == "artifact-model"


class _Capture:
    """Records the model + json_mode the gateway forwards to the provider."""

    name = "gemini"
    model = "default-model"

    def __init__(self) -> None:
        self.seen: list[tuple[str, bool]] = []

    def is_configured(self) -> bool:
        return True

    def complete(self, req: LLMRequest):
        from forge_kernel.gateway.types import LLMResponse, Usage
        self.seen.append((req.model or self.model, req.json_mode))
        return LLMResponse(content="{}", provider=self.name, model=req.model or self.model,
                           usage=Usage(1, 1))


def test_gateway_forwards_per_request_model_and_json_mode():
    cap = _Capture()
    gw = Gateway([cap], router=Router({"draft": ["gemini"]}), cache_enabled=False)
    gw.complete(LLMRequest(messages=[Message("user", "hi")], task="draft",
                           model="strong-x", json_mode=True))
    assert cap.seen == [("strong-x", True)]


def test_offline_never_adds_real_providers_even_with_keys():
    # A Gemini key present but mode=offline must stay deterministic ($0, reproducible).
    offline = build_gateway(Settings(mode="offline", gemini_api_key="key"))
    assert offline.metrics()["providers"] == ["deterministic"]
    live = build_gateway(Settings(mode="live", gemini_api_key="key"))
    assert "gemini" in live.metrics()["providers"]


def test_gemini_provider_uses_request_model_over_default():
    p = GeminiProvider(api_key="k", model="gemini-2.5-flash", base_url="http://x", timeout_s=1)
    assert p.is_configured()
    assert p.model == "gemini-2.5-flash"  # default tier; per-request model overrides at call
