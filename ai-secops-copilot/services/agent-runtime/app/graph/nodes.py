"""LangGraph nodes.

Day-1 scaffold: structure and contracts are in place. The Finding Analysis Node
is a stub until Day 2 (it will call the AI Gateway, then validate the structured
output via schemas.AnalysisResult). The Governance Gate already uses the real
governance logic so the end-to-end shape is correct from the start.
"""

from __future__ import annotations

from .. import governance
from ..config import get_settings
from ..domain import Action
from ..idempotency import finding_hash
from .state import GraphState


def ingest_node(state: GraphState) -> GraphState:
    """Compute the idempotency key before any analysis (ADR-009)."""
    finding = state.get("finding", {})
    state["finding_hash"] = finding_hash(finding)
    state.setdefault("retries", 0)
    state.setdefault("errors", [])
    return state


def finding_analysis_node(state: GraphState) -> GraphState:
    """Analyze the finding into {severity, confidence, reason, recommendedAction}.

    TODO(Day 2): call the AI Gateway (single LLM egress), pass RAG context
    (Day 5), validate the response with schemas.AnalysisResult, and bounded-retry
    on invalid structured output. Finding text is treated as UNTRUSTED input and
    must be isolated from system instructions (ADR-011).
    """
    raise NotImplementedError(
        "finding_analysis_node is a Day-1 scaffold stub. "
        "Day 2 wires the AI Gateway call + structured-output validation."
    )


def ticket_decision_node(state: GraphState) -> GraphState:
    """Apply the Governance Gate to the analysis to produce a TicketDecision.

    This node is functional: given a validated analysis it produces a governed
    decision. (Auto-execute / human-approval / escalate.)
    """
    settings = get_settings()
    analysis = state.get("analysis")
    if not analysis:
        state.setdefault("errors", []).append("ticket_decision_node: missing analysis")
        return state

    decision = governance.evaluate(
        confidence=float(analysis["confidence"]),
        recommended_action=Action(analysis["recommendedAction"]),
        auto_threshold=settings.auto_threshold,
        suggest_threshold=settings.suggest_threshold,
    )

    state["decision"] = {
        "findingId": state.get("finding", {}).get("id"),
        "findingHash": state.get("finding_hash"),
        "analysis": analysis,
        "disposition": decision.disposition.value,
        "requiresHuman": decision.requires_human,
        "governanceReason": decision.reason,
    }
    return state
