"""Forge kernel — the generic, domain-agnostic multi-agent engine.

The kernel knows nothing about product development. It executes a **Blueprint** (a
data-driven DAG of stages and artifacts) by scheduling agents in parallel, enforcing
quality (eval-as-gate) and human (HITL) gates, accounting cost/time against a budget
governor, and writing an append-only audit trail — all over a shared **RunState**
blackboard, with a single LLM egress (the AI Gateway).

Point the same kernel at any project by loading a different blueprint + skill packs.
``forge_os`` is one such program (the product-development lifecycle).

Everything here is stdlib-importable and runs offline-deterministic with no API keys.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
