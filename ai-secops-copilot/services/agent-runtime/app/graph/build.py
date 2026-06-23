"""Build the compiled LangGraph agent (Day 9).

Upgrades the Day-2 walking skeleton from straight-line node calls to a real compiled
StateGraph with **explicit state**, **conditional routing** on the governance
disposition, **checkpointing**, and a **human-in-the-loop interrupt** for the approval
gate (ADR-004, ADR-005).

    ingest -> finding_analysis -> ticket_decision -> route on disposition:
        auto_execute / escalate  -> execute        -> END
        human_approval           -> await_approval  -> (interrupt) -> END

The analysis/decision nodes are the same functions used by the dependency-free
``pipeline.run_pipeline`` fallback, so there is one source of truth for the reasoning;
only the action stage (which needs the ticketing stores) is wired here as closures.

LangGraph is imported lazily so the rest of the package stays importable without it.
"""

from __future__ import annotations

from typing import Any

from ..ticketing import (
    ActionResult,
    ApprovalStore,
    DeadLetterQueue,
    EscalationQueue,
    TicketProvider,
    execute_decision,
)
from .nodes import finding_analysis_node, ingest_node, ticket_decision_node
from .state import GraphState


def _route_on_disposition(state: GraphState) -> str:
    """Conditional edge: send the decision to the right action node."""
    disposition = str((state.get("decision") or {}).get("disposition", ""))
    if disposition == "human_approval":
        return "await_approval"
    return "execute"  # auto_execute + escalate (and any unexpected) are non-interrupting


def build_agent_graph(
    *,
    provider: TicketProvider,
    approvals: ApprovalStore,
    escalations: EscalationQueue,
    dead_letter: DeadLetterQueue | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Construct and compile the agent graph with the action stage wired to stores.

    Raises a clear error if LangGraph is not installed.
    """
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import interrupt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "langgraph is not installed. Install runtime deps: "
            "pip install -r services/agent-runtime/requirements.txt"
        ) from exc

    def execute_node(state: GraphState) -> GraphState:
        """Autonomous action: create the ticket / suppress / escalate (no human)."""
        action = execute_decision(
            state["decision"], provider=provider, approvals=approvals,
            escalations=escalations, dead_letter=dead_letter,
        )
        state["action"] = action.to_dict()
        return state

    def await_approval_node(state: GraphState) -> GraphState:
        """HITL gate: queue the decision, then PAUSE the graph for a human (interrupt).

        On resume the graph is re-entered with ``Command(resume={"approved": bool})``;
        approval creates the ticket, rejection records a rejected action. Because the
        node pauses at ``interrupt(...)`` the run can be checkpointed and resumed in a
        later request — the essence of durable human-in-the-loop orchestration.
        """
        decision = state["decision"]
        approvals.enqueue(decision)  # visible immediately, before the pause

        review = interrupt({
            "type": "approval_required",
            "findingHash": decision.get("findingHash"),
            "findingId": decision.get("findingId"),
            "severity": (decision.get("analysis") or {}).get("severity"),
            "reason": decision.get("governanceReason"),
        })

        approved = bool(review and review.get("approved"))
        if approved:
            ticket, created = provider.create(decision, via="approval")
            state["action"] = ActionResult(
                outcome="ticket_created" if created else "ticket_exists",
                disposition=str(decision.get("disposition", "")),
                findingHash=str(decision.get("findingHash", "")),
                ticket=ticket.to_dict(),
                detail="Human approved; ticket created.",
            ).to_dict()
        else:
            approvals.reject(str(decision.get("findingHash", "")))
            state["action"] = ActionResult(
                outcome="rejected",
                disposition=str(decision.get("disposition", "")),
                findingHash=str(decision.get("findingHash", "")),
                detail="Human rejected the decision; no ticket created.",
            ).to_dict()
        return state

    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("finding_analysis", finding_analysis_node)
    graph.add_node("ticket_decision", ticket_decision_node)
    graph.add_node("execute", execute_node)
    graph.add_node("await_approval", await_approval_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "finding_analysis")
    graph.add_edge("finding_analysis", "ticket_decision")
    graph.add_conditional_edges(
        "ticket_decision",
        _route_on_disposition,
        {"execute": "execute", "await_approval": "await_approval"},
    )
    graph.add_edge("execute", END)
    graph.add_edge("await_approval", END)

    return graph.compile(checkpointer=checkpointer)


def build_graph() -> Any:
    """Backwards-compatible builder (no stores): structure-only, for introspection."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("finding_analysis", finding_analysis_node)
    graph.add_node("ticket_decision", ticket_decision_node)
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "finding_analysis")
    graph.add_edge("finding_analysis", "ticket_decision")
    graph.add_edge("ticket_decision", END)
    return graph.compile()
