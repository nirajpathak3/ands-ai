"""End-to-end walking skeleton: Finding -> analysis -> governance -> action.

Runs the graph nodes as plain functions (so it works without LangGraph installed)
and then executes the governed decision through the mock ticketing layer. The
compiled LangGraph in ``graph/build.py`` wraps the same node functions; Day 9
upgrades the orchestration to the full graph with checkpointing and an interrupt,
without changing this contract.

    ingest (hash) -> finding_analysis (LLM + validate) -> ticket_decision
        (governance gate) -> execute (auto-ticket | approval queue | escalate)
"""

from __future__ import annotations

from collections.abc import Mapping

from .graph.nodes import finding_analysis_node, ingest_node, ticket_decision_node
from .graph.state import GraphState
from .llm import LLMClient
from .ticketing import (
    ApprovalStore,
    EscalationQueue,
    MockTicketProvider,
    execute_decision,
)


def run_pipeline(
    finding: Mapping[str, object],
    *,
    provider: MockTicketProvider,
    approvals: ApprovalStore,
    escalations: EscalationQueue,
    client: LLMClient | None = None,
) -> dict:
    """Process one finding end to end and execute the resulting decision.

    Returns ``{"decision": ..., "action": ..., "retries": int, "errors": [...]}``.
    """
    state: GraphState = {"finding": dict(finding)}
    if client is not None:
        state["_client"] = client  # type: ignore[typeddict-unknown-key]

    state = ingest_node(state)
    state = finding_analysis_node(state)
    state = ticket_decision_node(state)

    decision = state.get("decision", {})
    action = execute_decision(
        decision, provider=provider, approvals=approvals, escalations=escalations
    )

    return {
        "decision": decision,
        "action": action.to_dict(),
        "retries": state.get("retries", 0),
        "errors": state.get("errors", []),
    }
