"""LangGraph nodes.

Day 2 wires the walking skeleton: the Finding Analysis Node calls the LLM client
seam, validates the structured output (schemas.AnalysisResult), bounded-retries on
invalid output, and escalates if it never validates. The Governance Gate uses the
real governance logic, so the end-to-end shape is correct. RAG context (Day 5) and
the real LLM via the AI Gateway (Day 11) slot in behind the same seams.
"""

from __future__ import annotations

from .. import governance
from ..config import get_settings
from ..domain import Action
from ..idempotency import finding_hash
from ..llm import analyze_and_validate, get_default_client
from ..rag import format_context, get_default_retriever
from .state import GraphState


def ingest_node(state: GraphState) -> GraphState:
    """Compute the idempotency key before any analysis (ADR-009)."""
    finding = state.get("finding", {})
    state["finding_hash"] = finding_hash(finding)
    state.setdefault("retries", 0)
    state.setdefault("errors", [])
    return state


def _from_state_or_config(state: GraphState, config, key: str):
    """Resolve a runtime dependency (LLM client / retriever) from state or config.

    The inline pipeline injects via ``state['_<key>']``; the compiled graph injects via
    ``config['configurable'][<key>]`` so the object is NOT written to checkpointed state
    (LangGraph would fail to serialize an LLM client / retriever otherwise).
    """
    value = state.get(f"_{key}")
    if value is not None:
        return value
    if config:
        return (config.get("configurable") or {}).get(key)
    return None


def finding_analysis_node(state: GraphState, config=None) -> GraphState:  # noqa: ANN001
    # `config` is intentionally untyped: under `from __future__ import annotations`
    # a non-RunnableConfig annotation makes LangGraph skip config injection.
    """Analyze the finding into {severity, confidence, reason, recommendedAction}.

    Calls the LLM client (DeterministicLLM today; the AI Gateway on Day 11) and
    validates the structured output before it is allowed to drive any action
    (ADR-010). Finding text is treated as UNTRUSTED input, isolated from system
    instructions in prompts.py (ADR-011). On repeated invalid output the finding is
    escalated rather than acted on (PRODUCT_VISION failure handling).
    """
    settings = get_settings()
    finding = state.get("finding", {})
    client = _from_state_or_config(state, config, "client") or get_default_client()

    # RAG: retrieve OWASP/CWE guidance to ground the analysis and cite the decision
    # (ADR-001). The retrieved text is passed to the LLM prompt as TRUSTED context,
    # kept separate from the UNTRUSTED finding (ADR-011). The offline deterministic
    # client decides from rules; the citations still surface the grounding, and the
    # real LLM (Day 11) consumes the context via prompts.build_analysis_messages.
    if settings.rag_enabled:
        retriever = _from_state_or_config(state, config, "retriever") or get_default_retriever()
        if retriever is not None:
            try:
                hits = retriever.retrieve_for_finding(finding, k=settings.rag_top_k)
                state["rag_context"] = format_context(hits)
                state["citations"] = [h.to_citation() for h in hits]
            except Exception as exc:  # noqa: BLE001 - retrieval is best-effort grounding
                state.setdefault("errors", []).append(f"rag_retrieval: {exc}")

    result, attempts, error = analyze_and_validate(
        finding, client, max_retries=settings.analysis_max_retries
    )
    state["retries"] = attempts

    if result is None:
        state.setdefault("errors", []).append(
            f"finding_analysis_node: invalid model output after {attempts} attempt(s): {error}"
        )
        state["analysis"] = {
            "severity": "medium",
            "confidence": 0.0,
            "reason": (
                "Model output failed structured-output validation after bounded "
                f"retries ({error}); escalating for human review."
            ),
            "recommendedAction": Action.ESCALATE.value,
        }
        return state

    state["analysis"] = result.model_dump(mode="json")
    return state


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
        suppress_auto_threshold=settings.suppress_auto_threshold,
    )

    state["decision"] = {
        "findingId": state.get("finding", {}).get("id"),
        "findingHash": state.get("finding_hash"),
        "analysis": analysis,
        "disposition": decision.disposition.value,
        "requiresHuman": decision.requires_human,
        "governanceReason": decision.reason,
        "reasonCode": decision.reason_code.value,
        "citations": state.get("citations", []),
    }
    return state
