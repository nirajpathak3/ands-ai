"""Shared LangGraph state.

The graph threads a single mutable state dict through the nodes. Using a
TypedDict keeps it stdlib-importable (TypedDict is in typing) while documenting
the contract each node reads/writes.
"""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    # Inputs
    finding: dict[str, Any]      # normalized finding (see schemas.Finding)
    finding_hash: str            # idempotency key (ADR-009)

    # Produced by the Finding Analysis Node
    analysis: dict[str, Any]     # validated AnalysisResult as a dict

    # Produced by the Ticket Decision Node + Governance Gate
    decision: dict[str, Any]     # TicketDecision as a dict

    # Produced by the RAG layer (Day 5)
    rag_context: str | None      # retrieved OWASP/CWE context (for the LLM prompt)
    citations: list[dict[str, Any]]  # retrieved knowledge references (grounding)

    # Control / observability
    retries: int                 # bounded re-prompt counter for invalid output
    errors: list[str]
