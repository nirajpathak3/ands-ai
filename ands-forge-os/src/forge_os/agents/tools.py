"""Tool steps for tool-using agents (mockup, scaffolder).

After an agent has produced validated structured content, these turn that content (plus
scoped inputs) into a concrete artifact on disk via the kernel tool ports, and return the
path + extra fields to merge back into the artifact record. Kept separate from the agent so
the LLM/structured-output logic stays generic and the tool invocation stays explicit.
"""

from __future__ import annotations

from forge_kernel.agents import AgentContext

from .seeds import product_label


def render_mockup_step(ctx: AgentContext, content: dict) -> tuple[str, dict]:
    product = product_label(ctx.run.vision)
    personas = [
        {"name": "Primary user", "goal": "Reach the core value moment fast."},
        {"name": "Secondary user", "goal": "Oversee and approve outcomes."},
    ]
    personas_art = ctx.inputs.get("personas")
    if personas_art and isinstance(personas_art.content, dict):
        personas[0]["goal"] = str(personas_art.content.get("goals", personas[0]["goal"]))
    screens = [
        {"name": "Onboarding", "sections": ["Welcome", "Connect data"], "cta": "Get started"},
        {"name": "Dashboard", "sections": ["Overview", "Key metrics", "Activity"],
         "cta": "Create"},
        {"name": "Detail", "sections": ["Summary", "Actions", "History"], "cta": "Approve"},
    ]
    out = ctx.tools.invoke(
        "render_mockup", title=product, subtitle="MVP mockup rendered by ANDS Forge OS",
        personas=personas, screens=screens, path="ux/mockup.html",
    )
    return out["path"], {"mockupPath": out["path"]}


def scaffold_repo_step(ctx: AgentContext, content: dict) -> tuple[str, dict]:
    product = product_label(ctx.run.vision)
    endpoints = [
        {"method": "GET", "path": "/health", "purpose": "Liveness check"},
        {"method": "POST", "path": "/items", "purpose": "Create a core entity"},
        {"method": "GET", "path": "/items", "purpose": "List core entities"},
    ]
    entities = [{"name": "Item", "fields": "id, name, created_at"}]
    out = ctx.tools.invoke(
        "scaffold_repo", name=product, summary=f"Scaffolded product for: {ctx.run.vision}",
        endpoints=endpoints, entities=entities,
    )
    return out["repo"], {"repo": out["repo"], "files": out["files"]}
