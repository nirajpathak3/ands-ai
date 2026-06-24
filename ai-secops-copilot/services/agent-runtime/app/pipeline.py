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
from contextlib import nullcontext

from .graph.nodes import finding_analysis_node, ingest_node, ticket_decision_node
from .graph.state import GraphState
from .llm import LLMClient
from .rag import KnowledgeRetriever
from .ticketing import (
    ApprovalStore,
    DeadLetterQueue,
    EscalationQueue,
    TicketProvider,
    execute_decision,
)


def _get_tracer():
    try:
        from .observability import get_tracer

        return get_tracer()
    except Exception:  # noqa: BLE001 - tracing is best-effort
        return None


def _span(tracer, name: str, **attrs):
    return tracer.start_span(name, **attrs) if tracer is not None else nullcontext()


def run_pipeline(
    finding: Mapping[str, object],
    *,
    provider: TicketProvider,
    approvals: ApprovalStore,
    escalations: EscalationQueue,
    dead_letter: DeadLetterQueue | None = None,
    client: LLMClient | None = None,
    retriever: KnowledgeRetriever | None = None,
    policy: object | None = None,
) -> dict:
    """Process one finding end to end and execute the resulting decision.

    Returns ``{"decision": ..., "action": ..., "retries": int, "errors": [...]}``.
    """
    state: GraphState = {"finding": dict(finding)}
    if client is not None:
        state["_client"] = client  # type: ignore[typeddict-unknown-key]
    if retriever is not None:
        state["_retriever"] = retriever  # type: ignore[typeddict-unknown-key]
    if policy is not None:
        state["_policy"] = policy  # type: ignore[typeddict-unknown-key]

    tracer = _get_tracer()
    with _span(tracer, "pipeline.run", findingId=str(finding.get("id", ""))):
        with _span(tracer, "ingest"):
            state = ingest_node(state)
        with _span(tracer, "finding_analysis"):
            state = finding_analysis_node(state)
        with _span(tracer, "ticket_decision"):
            state = ticket_decision_node(state)

        decision = state.get("decision", {})
        with _span(tracer, "execute"):
            action = execute_decision(
                decision, provider=provider, approvals=approvals,
                escalations=escalations, dead_letter=dead_letter,
            )

    return {
        "decision": decision,
        "action": action.to_dict(),
        "retries": state.get("retries", 0),
        "errors": state.get("errors", []),
    }
