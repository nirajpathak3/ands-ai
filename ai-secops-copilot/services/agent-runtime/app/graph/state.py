"""Shared LangGraph state.

The graph threads a single mutable state dict through the nodes. Using a
TypedDict keeps it stdlib-importable (TypedDict is in typing) while documenting
the contract each node reads/writes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # Inputs
    finding: Dict[str, Any]      # normalized finding (see schemas.Finding)
    finding_hash: str            # idempotency key (ADR-009)

    # Produced by the Finding Analysis Node
    analysis: Dict[str, Any]     # validated AnalysisResult as a dict

    # Produced by the Ticket Decision Node + Governance Gate
    decision: Dict[str, Any]     # TicketDecision as a dict

    # Control / observability
    retries: int                 # bounded re-prompt counter for invalid output
    errors: List[str]
    rag_context: Optional[str]   # retrieved OWASP/CWE context (Day 5)
