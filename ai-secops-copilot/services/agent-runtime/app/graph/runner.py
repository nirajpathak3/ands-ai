"""Run the compiled LangGraph agent with checkpointing + resumable HITL (Day 9).

``GraphRunner`` owns a compiled graph plus an in-memory checkpointer so a run that
hits the human-approval interrupt can be **paused in one request and resumed in
another** (keyed by ``thread_id``). The same instance is reused across requests so the
checkpointed state survives between ``analyze`` and ``resume``.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..llm import LLMClient
from ..rag import KnowledgeRetriever
from ..ticketing import ApprovalStore, DeadLetterQueue, EscalationQueue, TicketProvider
from .build import build_agent_graph


class GraphRunner:
    def __init__(
        self,
        *,
        provider: TicketProvider,
        approvals: ApprovalStore,
        escalations: EscalationQueue,
        dead_letter: DeadLetterQueue | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        if checkpointer is None:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()
        self._checkpointer = checkpointer
        self._graph = build_agent_graph(
            provider=provider, approvals=approvals, escalations=escalations,
            dead_letter=dead_letter, checkpointer=self._checkpointer,
        )

    def _config(
        self,
        thread_id: str,
        *,
        client: LLMClient | None = None,
        retriever: KnowledgeRetriever | None = None,
        policy: object | None = None,
    ) -> dict:
        # client/retriever/policy go in config (runtime) so they are NOT checkpointed —
        # LangGraph's serializer cannot persist these live objects.
        return {
            "configurable": {
                "thread_id": thread_id,
                "client": client,
                "retriever": retriever,
                "policy": policy,
            }
        }

    @staticmethod
    def _interrupt_payload(result: dict) -> dict | None:
        """Extract the interrupt value, if the run paused for approval."""
        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        if not interrupts:
            return None
        first = interrupts[0]
        return getattr(first, "value", first)

    def _finalize(self, thread_id: str, result: dict) -> dict:
        payload = self._interrupt_payload(result)
        if payload is not None:
            return {
                "status": "awaiting_approval",
                "threadId": thread_id,
                "decision": result.get("decision"),
                "interrupt": payload,
            }
        return {
            "status": "completed",
            "threadId": thread_id,
            "decision": result.get("decision"),
            "action": result.get("action"),
            "retries": result.get("retries", 0),
            "errors": result.get("errors", []),
        }

    def analyze(
        self,
        finding: dict,
        *,
        thread_id: str | None = None,
        client: LLMClient | None = None,
        retriever: KnowledgeRetriever | None = None,
        policy: object | None = None,
    ) -> dict:
        """Run a finding through the graph; pause at the HITL gate if required."""
        thread_id = thread_id or uuid.uuid4().hex
        state: dict[str, Any] = {"finding": dict(finding)}
        config = self._config(
            thread_id, client=client, retriever=retriever, policy=policy
        )
        result = self._graph.invoke(state, config)
        return self._finalize(thread_id, result)

    def resume(self, thread_id: str, *, approved: bool) -> dict:
        """Resume a paused run with the human's approve/reject decision."""
        from langgraph.types import Command

        snapshot = self._graph.get_state(self._config(thread_id))
        if not snapshot.next:
            raise KeyError(thread_id)
        result = self._graph.invoke(
            Command(resume={"approved": approved}), self._config(thread_id)
        )
        return self._finalize(thread_id, result)

    def mermaid(self) -> str:
        """Mermaid source for the compiled graph (demo / docs)."""
        return self._graph.get_graph().draw_mermaid()

    def nodes(self) -> list[str]:
        return list(self._graph.get_graph().nodes)
