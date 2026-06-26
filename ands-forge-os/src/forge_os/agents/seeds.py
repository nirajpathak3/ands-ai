"""Deterministic artifact seeds.

A *seed* is the reproducible, offline content for an artifact: a dict whose fields line up
with the artifact's rubric. Offline, the AI Gateway's deterministic provider echoes the
seed verbatim ($0, reproducible) — so the kernel exercises the full structured-output path
without a model. In live mode the seed becomes the **graceful fallback** if a real model
never returns valid structured output, so a run never hard-fails on a bad generation.

These are pure functions of the blackboard, so the whole run stays reproducible.
"""

from __future__ import annotations

from forge_kernel.agents import AgentContext


def product_label(vision: str) -> str:
    words = (vision or "the product").strip().split()
    label = " ".join(words[:8])
    return label[:80] or "the product"


def _base(ctx: AgentContext, values: dict[str, object]) -> dict:
    """Fill any rubric criterion not explicitly provided with grounded placeholder text."""
    product = product_label(ctx.run.vision)
    content: dict[str, object] = {}
    for crit in ctx.spec.rubric:
        pretty = crit.replace("_", " ")
        content[crit] = values.get(crit, f"{pretty.capitalize()} for {product}.")
    if not ctx.spec.rubric:
        content.update(values)
    return content


def seed_vision_brief(ctx: AgentContext) -> dict:
    product = product_label(ctx.run.vision)
    return _base(ctx, {
        "problem": f"The core problem framed from the vision: {product}.",
        "audience": "Primary audience inferred from the vision statement.",
        "success_metrics": "Adoption, activation, and time-to-value targets.",
        "constraints": "Offline-first, deterministic, budget-bounded delivery.",
        "non_goals": "No scope beyond the MVP vertical slice.",
    })


def seed_prd(ctx: AgentContext) -> dict:
    inputs = ", ".join(sorted(ctx.inputs)) or "discovery"
    content = _base(ctx, {
        "problem": f"Problem statement synthesized from {inputs}.",
        "features": "Prioritized MVP feature set traceable to user needs.",
        "metrics": "Success metrics with target thresholds.",
        "scope": "In-scope for v1; explicit non-scope deferred.",
    })
    content["_traces_to"] = sorted(ctx.inputs)
    return content


def seed_mockup(ctx: AgentContext) -> dict:
    return _base(ctx, {
        "screens": ["Onboarding", "Dashboard", "Detail"],
        "layout": "Three-screen flow: onboarding -> dashboard -> detail.",
        "cta": ["Get started", "Create", "Approve"],
    })


def seed_scaffold(ctx: AgentContext) -> dict:
    product = product_label(ctx.run.vision)
    return _base(ctx, {
        "readme": f"README generated for {product}.",
        "structure": "app/, tests/, evals/ with a FastAPI skeleton.",
        "tests": "Health-check test included.",
    })


def seed_generic(ctx: AgentContext) -> dict:
    return _base(ctx, {})
