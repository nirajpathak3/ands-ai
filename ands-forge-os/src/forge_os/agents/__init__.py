"""ANDS Forge OS agent roster.

One unified, skill-pack-driven ``LLMArtifactAgent`` backs every role in both modes:
* OFFLINE — the AI Gateway's deterministic provider echoes a reproducible seed ($0).
* LIVE    — a real provider generates, validated against a structured-output contract with
  bounded reprompt and a graceful fallback to the seed.
"""

from __future__ import annotations

from .llm_agent import LLMArtifactAgent, build_registry

__all__ = ["build_registry", "LLMArtifactAgent"]
