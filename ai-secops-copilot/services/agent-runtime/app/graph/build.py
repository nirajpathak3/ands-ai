"""Build the LangGraph state graph.

Wiring:  ingest -> finding_analysis -> ticket_decision -> END

LangGraph is imported lazily so the rest of the package (governance, schemas,
idempotency) stays importable without the dependency installed. Checkpointing
and the human-approval interrupt are added on later days (Day 10).
"""

from __future__ import annotations

from typing import Any

from .nodes import finding_analysis_node, ingest_node, ticket_decision_node
from .state import GraphState


def build_graph() -> Any:
    """Construct and compile the agent graph.

    Raises a clear error if LangGraph is not installed yet.
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "langgraph is not installed. Install runtime deps: "
            "pip install -r services/agent-runtime/requirements.txt"
        ) from exc

    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("finding_analysis", finding_analysis_node)
    graph.add_node("ticket_decision", ticket_decision_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "finding_analysis")
    graph.add_edge("finding_analysis", "ticket_decision")
    graph.add_edge("ticket_decision", END)

    return graph.compile()
