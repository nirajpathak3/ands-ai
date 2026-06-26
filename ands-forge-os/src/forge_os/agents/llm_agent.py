"""LLMArtifactAgent — one skill-pack-driven agent for both offline and live modes.

This is build-step 4: real agents. A single generic agent drives every text artifact:

  1. Build messages from the skill pack policy + scoped inputs, with the untrusted vision
     fenced off (prompts.build_messages, ADR-011) and a strict JSON output contract.
  2. Call the AI Gateway (task="draft").
       * OFFLINE: pass the deterministic ``seed`` so the deterministic provider echoes a
         reproducible, rubric-shaped artifact ($0) — the walking-skeleton path.
       * LIVE: a real provider generates; we parse + validate the JSON and **reprompt** up
         to ``analysis_max_retries`` times on invalid output (ADR-010).
  3. If the model never returns valid structured output, **fall back to the seed** so the
     run degrades gracefully instead of acting on garbage.
  4. Optionally run a tool (render_mockup / scaffold_repo) using the validated content.

Same agent, same contract, both modes — the deterministic stubs are now simply the offline
seed path of the real agent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from forge_kernel.agents import AgentContext, AgentRegistry, AgentResult
from forge_kernel.gateway import LLMRequest
from forge_kernel.model_policy import resolve_model

from ..prompts import build_messages
from ..structured import extract_json, validate_required
from . import seeds
from . import tools as tool_steps

SeedFn = Callable[[AgentContext], dict]
ToolFn = Callable[[AgentContext, dict], tuple[str, dict]]


@dataclass
class _Generation:
    """Result of the structured-output loop, including which provider actually served."""

    content: dict
    cost_usd: float
    tokens: int
    attempts: int
    error: str
    provider: str | None  # the provider/model that produced the returned content (the
    model: str | None      # last call) — reflects gateway fallback (e.g. gemini -> groq).


def _generate_structured(ctx: AgentContext, seed: dict) -> _Generation:
    """Run the structured-output loop, tracking the provider that served the final call."""
    required = list(ctx.spec.rubric)
    offline = ctx.settings.offline
    max_retries = ctx.settings.analysis_max_retries
    # Which model does this stage? blueprint override -> task/stage tier -> provider default.
    model = resolve_model(
        ctx.settings, task="draft", stage=ctx.spec.stage, override=ctx.spec.model
    )
    total_cost = 0.0
    total_tokens = 0
    nudge = ""
    last_error = ""
    served_provider: str | None = None
    served_model: str | None = None

    for attempt in range(max_retries + 1):
        messages = build_messages(ctx, required, nudge=nudge)
        # Offline: hand the provider the seed to echo. Live: let the real model generate.
        payload = {"seed": seed} if offline else None
        # Exact cache only: structured prompts for different artifacts are near-identical
        # (shared contract boilerplate) and would fuzzy-collide, returning the wrong keys.
        result = ctx.gateway.complete(LLMRequest(
            messages=messages, task="draft", payload=payload, cache="exact",
            model=model, json_mode=not offline,
        ))
        total_cost += result.cost_usd
        total_tokens += result.response.usage.total_tokens
        served_provider, served_model = result.provider, result.model

        parsed = extract_json(result.response.content)
        missing = validate_required(parsed, required)
        if not missing:
            content = dict(seed)
            content.update(parsed or {})  # model output wins; seed backfills any extras
            return _Generation(content, total_cost, total_tokens, attempt + 1, "",
                               served_provider, served_model)
        last_error = f"missing/empty keys: {missing}"
        nudge = (
            f"Your previous response was invalid ({last_error}). Return ONLY a JSON object "
            f"with non-empty values for: {required}."
        )

    # Never returned valid structured output -> graceful fallback to the deterministic seed.
    fallback = dict(seed)
    fallback["_fallback"] = f"model output invalid after {max_retries + 1} attempts ({last_error})"
    return _Generation(fallback, total_cost, total_tokens, max_retries + 1, last_error,
                       served_provider, served_model)


class LLMArtifactAgent:
    """Generic skill-pack-driven agent (text + optional tool step)."""

    def __init__(self, role: str, seed_fn: SeedFn, *, tool_fn: ToolFn | None = None) -> None:
        self.role = role
        self._seed_fn = seed_fn
        self._tool_fn = tool_fn

    def run(self, ctx: AgentContext) -> AgentResult:
        seed = self._seed_fn(ctx)
        gen = _generate_structured(ctx, seed)
        content = gen.content

        feedback = ctx.run.feedback.get(ctx.spec.stage)
        if feedback:
            content["_revision_note"] = f"Revised per human feedback: {feedback}"

        path: str | None = None
        if self._tool_fn is not None:
            path, extra = self._tool_fn(ctx, content)
            content.update(extra)

        citations: list[dict] = []
        if ctx.skillpack and ctx.skillpack.corpus:
            citations = [{"source": c} for c in ctx.skillpack.corpus]

        note = f"{ctx.spec.title} produced by {ctx.spec.role}"
        note += f" ({'offline' if ctx.settings.offline else 'live'}, {gen.attempts} attempt(s))"
        if gen.provider:
            note += f" via {gen.provider}"
        if gen.error:
            note += f" [fallback: {gen.error}]"
        return AgentResult(
            content=content, citations=citations, cost_usd=gen.cost_usd, tokens=gen.tokens,
            path=path, notes=note,
            served_provider=gen.provider, served_model=gen.model,
        )


# --- side-effect seed: surface the Vision Brief on the blackboard -------------


def _vision_brief_seed(ctx: AgentContext) -> dict:
    seed = seeds.seed_vision_brief(ctx)
    ctx.run.vision_brief = seed
    return seed


# --- roster -------------------------------------------------------------------

_SEEDS: dict[str, SeedFn] = {
    "vision-intake": _vision_brief_seed,
    "prd-author": seeds.seed_prd,
    "mockup": seeds.seed_mockup,
    "scaffolder": seeds.seed_scaffold,
}

_TOOLS: dict[str, ToolFn] = {
    "mockup": tool_steps.render_mockup_step,
    "scaffolder": tool_steps.scaffold_repo_step,
}


def build_registry() -> AgentRegistry:
    """The ANDS Forge OS roster: one unified agent per role (offline + live)."""
    registry = AgentRegistry(
        default_factory=lambda role: LLMArtifactAgent(role, seeds.seed_generic)
    )
    roles = (
        "vision-intake", "user-research", "competitive-analysis", "business-case",
        "prd-author", "ai-capability-mapper", "persona", "user-flow", "mockup",
        "system-architect", "api-spec", "db-schema", "scaffolder",
    )
    for role in roles:
        registry.register(
            LLMArtifactAgent(role, _SEEDS.get(role, seeds.seed_generic),
                             tool_fn=_TOOLS.get(role))
        )
    return registry
