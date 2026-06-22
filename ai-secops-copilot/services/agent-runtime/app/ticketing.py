"""Mock ticketing + human-approval layer (the walking skeleton's action stage).

Day 2 keeps this in-memory and provider-agnostic so the full flow
(governance decision -> action) runs with no external systems:

  * AUTO_EXECUTE   -> create a ticket immediately (idempotent).
  * HUMAN_APPROVAL -> queue for a human; a ticket is created only on approval.
  * ESCALATE       -> route to an escalation queue (never auto-ticketed).

Idempotency (ADR-009): tickets are keyed by ``findingHash``. Re-processing the same
finding (retries, at-least-once delivery) returns the existing ticket instead of
opening a duplicate.

On Day 3 the ``TicketProvider`` protocol is implemented by a real Jira adapter and a
ServiceNow mock behind the MCP tool layer; the governance/pipeline code above does
not change.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass
class Ticket:
    key: str
    findingId: str | None
    findingHash: str
    severity: str
    summary: str
    status: str = "open"
    createdVia: str = "auto"  # "auto" | "approval"

    def to_dict(self) -> dict:
        return asdict(self)


class TicketProvider(Protocol):
    """Provider-agnostic ticket sink (real Jira / ServiceNow mock arrive Day 3)."""

    def create(self, decision: Mapping[str, object], *, via: str) -> tuple[Ticket, bool]:
        ...


class MockTicketProvider:
    """In-memory, idempotent ticket store keyed by ``findingHash``."""

    def __init__(self, prefix: str = "SEC") -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)
        self._by_hash: dict[str, Ticket] = {}

    def create(self, decision: Mapping[str, object], *, via: str = "auto") -> tuple[Ticket, bool]:
        """Create a ticket for the decision, or return the existing one (idempotent).

        Returns ``(ticket, created)`` where ``created`` is False on a duplicate.
        """
        finding_hash = str(decision.get("findingHash", ""))
        existing = self._by_hash.get(finding_hash)
        if existing is not None:
            return existing, False

        analysis = decision.get("analysis") or {}
        severity = (
            str(analysis.get("severity", "unknown"))
            if isinstance(analysis, Mapping) else "unknown"
        )
        finding_id = decision.get("findingId")
        ticket = Ticket(
            key=f"{self._prefix}-{next(self._counter)}",
            findingId=str(finding_id) if finding_id is not None else None,
            findingHash=finding_hash,
            severity=severity,
            summary=f"[{severity.upper()}] {finding_id}: security finding requires remediation",
            createdVia=via,
        )
        self._by_hash[finding_hash] = ticket
        return ticket, True

    def get(self, finding_hash: str) -> Ticket | None:
        return self._by_hash.get(finding_hash)

    def all(self) -> list[Ticket]:
        return list(self._by_hash.values())


@dataclass
class PendingApproval:
    findingHash: str
    decision: dict


class ApprovalStore:
    """Queue of decisions awaiting human approval (the HITL gate)."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def enqueue(self, decision: Mapping[str, object]) -> PendingApproval:
        finding_hash = str(decision.get("findingHash", ""))
        item = PendingApproval(findingHash=finding_hash, decision=dict(decision))
        self._pending[finding_hash] = item
        return item

    def list_pending(self) -> list[PendingApproval]:
        return list(self._pending.values())

    def get(self, finding_hash: str) -> PendingApproval | None:
        return self._pending.get(finding_hash)

    def approve(self, finding_hash: str, provider: TicketProvider) -> tuple[Ticket, bool]:
        """Approve a pending decision: create the ticket and dequeue it."""
        item = self._pending.pop(finding_hash, None)
        if item is None:
            raise KeyError(finding_hash)
        return provider.create(item.decision, via="approval")

    def reject(self, finding_hash: str) -> bool:
        return self._pending.pop(finding_hash, None) is not None


class EscalationQueue:
    """Findings routed to a human analyst (ambiguous / low confidence)."""

    def __init__(self) -> None:
        self._items: list[dict] = []

    def add(self, decision: Mapping[str, object]) -> None:
        self._items.append(dict(decision))

    def list_all(self) -> list[dict]:
        return list(self._items)


@dataclass
class ActionResult:
    # ticket_created | ticket_exists | suppressed | pending_approval | escalated
    outcome: str
    disposition: str
    findingHash: str
    ticket: dict | None = None
    detail: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        if data.get("ticket") is None:
            data.pop("ticket")
        return data


def _recommended_action(decision: Mapping[str, object]) -> str:
    analysis = decision.get("analysis") or {}
    if isinstance(analysis, Mapping):
        return str(analysis.get("recommendedAction", ""))
    return ""


def execute_decision(
    decision: Mapping[str, object],
    *,
    provider: MockTicketProvider,
    approvals: ApprovalStore,
    escalations: EscalationQueue,
) -> ActionResult:
    """Carry out a governed decision through the (mock) ticketing layer.

    The governance *disposition* decides the autonomy level; the analysis
    *recommendedAction* decides what is actually executed. A high-confidence
    suppression is auto-applied (no ticket); only a recommended ``create_ticket``
    ever opens a ticket.
    """
    disposition = str(decision.get("disposition", ""))
    finding_hash = str(decision.get("findingHash", ""))
    action = _recommended_action(decision)

    if disposition == "auto_execute":
        if action == "suppress":
            return ActionResult(
                outcome="suppressed",
                disposition=disposition,
                findingHash=finding_hash,
                detail="Auto-suppressed false positive (high confidence); no ticket created.",
            )
        ticket, created = provider.create(decision, via="auto")
        return ActionResult(
            outcome="ticket_created" if created else "ticket_exists",
            disposition=disposition,
            findingHash=finding_hash,
            ticket=ticket.to_dict(),
            detail=("Auto-created ticket (high confidence)." if created
                    else "Idempotent: ticket already exists for this finding."),
        )

    if disposition == "human_approval":
        approvals.enqueue(decision)
        verb = "suppress" if action == "suppress" else "create a ticket"
        return ActionResult(
            outcome="pending_approval",
            disposition=disposition,
            findingHash=finding_hash,
            detail=f"Queued for human approval to {verb} (medium confidence).",
        )

    # escalate (or anything unexpected) -> human review, no ticket.
    escalations.add(decision)
    return ActionResult(
        outcome="escalated",
        disposition=disposition or "escalate",
        findingHash=finding_hash,
        detail="Routed to a human analyst (ambiguous / low confidence).",
    )
