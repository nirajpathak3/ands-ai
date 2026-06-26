"""Step-4 real agents: structured-output parsing, the live path, reprompt, and fallback."""

from __future__ import annotations

import json

from forge_kernel.agents import AgentContext
from forge_kernel.blueprint import ArtifactSpec
from forge_kernel.config import Settings
from forge_kernel.gateway import Gateway, LLMRequest, LLMResponse, Usage
from forge_kernel.state import RunState
from forge_kernel.tools import default_tools
from forge_os.agents.llm_agent import LLMArtifactAgent
from forge_os.agents.seeds import seed_generic
from forge_os.structured import extract_json, validate_required

# --- pure parser --------------------------------------------------------------


def test_extract_json_plain_and_fenced_and_embedded():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('Sure! Here you go: {"a": 3} — done.') == {"a": 3}
    assert extract_json("not json at all") is None


def test_validate_required_flags_missing_and_empty():
    assert validate_required({"a": "x", "b": "y"}, ["a", "b"]) == []
    assert validate_required({"a": "x", "b": ""}, ["a", "b"]) == ["b"]
    assert validate_required(None, ["a"]) == ["a"]


# --- scripted providers -------------------------------------------------------


class _ScriptedProvider:
    """A fake 'openai' provider that returns a queue of canned completions."""

    name = "openai"
    model = "gpt-4o-mini"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def complete(self, req: LLMRequest) -> LLMResponse:
        self.calls += 1
        content = self._responses.pop(0) if self._responses else "{}"
        return LLMResponse(content=content, provider=self.name, model=self.model,
                           usage=Usage(prompt_tokens=10, completion_tokens=10))


def _scripted_gateway(responses: list[str]) -> Gateway:
    # Cache off: identical reprompts must re-hit the provider so attempt accounting is exact.
    return Gateway([_ScriptedProvider(responses)], cache_enabled=False)


def _ctx(gateway: Gateway, *, live: bool) -> AgentContext:
    spec = ArtifactSpec(key="prd", title="PRD", role="prd-author", stage="strategy",
                        rubric=("problem", "features", "metrics", "scope"))
    run = RunState.new("bp", "1", vision="A governed AI agent platform")
    settings = Settings(mode="live" if live else "offline", analysis_max_retries=2,
                        workspace="var")
    return AgentContext(spec=spec, run=run, settings=settings, gateway=gateway,
                        tools=default_tools("var"))


def test_live_path_parses_valid_model_json():
    valid = json.dumps({"problem": "p", "features": "f", "metrics": "m", "scope": "s"})
    gw = _scripted_gateway([valid])
    agent = LLMArtifactAgent("prd-author", seed_generic)
    result = agent.run(_ctx(gw, live=True))
    assert result.content["problem"] == "p"
    assert "_fallback" not in result.content
    assert "live, 1 attempt" in result.notes
    # The actual serving provider/model is captured (reflects gateway fallback).
    assert result.served_provider == "openai"
    assert result.served_model == "gpt-4o-mini"
    assert "via openai" in result.notes


def test_live_path_reprompts_then_succeeds():
    bad = '{"problem": "p"}'  # missing keys -> triggers a reprompt
    good = json.dumps({"problem": "p", "features": "f", "metrics": "m", "scope": "s"})
    gw = _scripted_gateway([bad, good])
    provider = gw._providers["openai"]
    agent = LLMArtifactAgent("prd-author", seed_generic)
    result = agent.run(_ctx(gw, live=True))
    assert provider.calls == 2  # one reprompt
    assert result.content["features"] == "f"
    assert "_fallback" not in result.content


def test_live_path_falls_back_to_seed_on_persistent_garbage():
    gw = _scripted_gateway(["nope", "still nope", "garbage"])
    provider = gw._providers["openai"]
    agent = LLMArtifactAgent("prd-author", seed_generic)
    result = agent.run(_ctx(gw, live=True))
    # max_retries=2 -> 3 attempts, then graceful fallback to the deterministic seed.
    assert provider.calls == 3
    assert "_fallback" in result.content
    assert result.content["problem"]  # seed backfilled the rubric


def test_offline_path_echoes_seed_without_a_model():
    from forge_kernel.gateway.providers import DeterministicProvider

    gw = Gateway([DeterministicProvider()])
    agent = LLMArtifactAgent("prd-author", seed_generic)
    result = agent.run(_ctx(gw, live=False))
    assert result.cost_usd == 0.0
    assert validate_required(result.content, ["problem", "features", "metrics", "scope"]) == []
    assert "offline, 1 attempt" in result.notes


# --- LLM-as-judge seam --------------------------------------------------------


def test_gateway_judge_is_noop_offline_and_blends_live():
    from forge_kernel.agents.reviewer import ReviewResult
    from forge_kernel.state import ArtifactRecord
    from forge_os.judge import make_gateway_judge

    spec = ArtifactSpec(key="prd", title="PRD", role="prd-author", stage="strategy",
                        rubric=("problem",))
    record = ArtifactRecord(key="prd", title="PRD", stage="strategy", role="prd-author",
                            content={"problem": "p"})
    heuristic = ReviewResult(critic_score=1.0, redteam_findings=[])

    # Offline -> no-op (deterministic), returns the heuristic unchanged.
    gw = Gateway([_ScriptedProvider(['{"score": 0.5, "findings": ["x"]}'])])
    judge_off = make_gateway_judge(gw, Settings(mode="offline"))
    assert judge_off(spec, record, heuristic).critic_score == 1.0

    # Live -> blends the model score (0.5) with the heuristic (1.0) -> 0.75.
    judge_live = make_gateway_judge(gw, Settings(mode="live"))
    blended = judge_live(spec, record, heuristic)
    assert blended.critic_score == 0.75
    assert blended.redteam_findings == ["x"]


def test_llm_judge_disabled_skips_model_call():
    from forge_kernel.agents.reviewer import ReviewResult
    from forge_kernel.state import ArtifactRecord
    from forge_os.judge import make_gateway_judge

    spec = ArtifactSpec(key="prd", title="PRD", role="prd-author", stage="strategy",
                        rubric=("problem",))
    record = ArtifactRecord(key="prd", title="PRD", stage="strategy", role="prd-author",
                            content={"problem": "p"})
    heuristic = ReviewResult(critic_score=1.0, redteam_findings=[])

    provider = _ScriptedProvider(['{"score": 0.5, "findings": ["x"]}'])
    gw = Gateway([provider])
    # Live but judge disabled -> heuristic returned unchanged, no model call made.
    judge = make_gateway_judge(gw, Settings(mode="live", llm_judge=False))
    assert judge(spec, record, heuristic).critic_score == 1.0
    assert provider.calls == 0
