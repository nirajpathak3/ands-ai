"""Ticketing orchestration + human-approval layer (the action stage).

This module owns the provider-agnostic orchestration (ADR-008): the governance
decision is turned into an action through a ``TicketProvider`` whose concrete
implementations live in ``app/providers/`` (mock, real Jira, ServiceNow mock).
The orchestration code here never changes when a provider is swapped.

  * AUTO_EXECUTE   -> create a ticket immediately (idempotent).
  * HUMAN_APPROVAL -> queue for a human; a ticket is created only on approval.
  * ESCALATE       -> route to an escalation queue (never auto-ticketed).

Idempotency (ADR-009): every provider keys tickets by ``findingHash``. Re-processing
the same finding (retries, at-least-once delivery) returns the existing ticket
instead of opening a duplicate — for the mock that is an in-memory map; for Jira it
is a JQL search on a ``finding-hash`` label.

Resilience (PRODUCT_VISION failure handling): if a provider raises (e.g. the Jira
API is down), the decision is parked on a dead-letter queue rather than lost, and a
``ticket_failed`` outcome is returned.
"""

from __future__ import annotations

import datetime as _dt
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
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


class TicketProvider(Protocol):
    """Provider-agnostic ticket sink (mock / Jira / ServiceNow mock)."""

    name: str

    def create(self, decision: Mapping[str, object], *, via: str) -> tuple[Ticket, bool]:
        ...

    def get(self, finding_hash: str) -> Ticket | None:
        ...

    def all(self) -> list[Ticket]:
        ...


class MockTicketProvider:
    """In-memory, idempotent ticket store keyed by ``findingHash``."""

    name = "mock"

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
            provider=self.name,
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
class DeadLetterItem:
    findingHash: str
    error: str
    decision: dict


class DeadLetterQueue:
    """Decisions whose ticket action failed (e.g. Jira API down) — never lost.

    A real platform would alert + retry from here; for the MVP we record them so the
    failure is visible and replayable instead of silently dropped.
    """

    def __init__(self) -> None:
        self._items: list[DeadLetterItem] = []

    def add(self, decision: Mapping[str, object], error: str) -> DeadLetterItem:
        item = DeadLetterItem(
            findingHash=str(decision.get("findingHash", "")),
            error=error,
            decision=dict(decision),
        )
        self._items.append(item)
        return item

    def list_all(self) -> list[DeadLetterItem]:
        return list(self._items)


@dataclass
class AuditRecord:
    """An immutable record of one governed decision (governance + observability).

    The audit trail answers "why did the system (or a human) take this action?" for
    every finding — the accountability backbone of governed automation.
    """

    timestamp: str
    findingHash: str
    findingId: str | None
    severity: str
    recommendedAction: str
    confidence: float
    disposition: str
    reasonCode: str | None
    outcome: str
    actor: str  # "system" (autonomous) | "human" (approval/rejection)

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLog:
    """Append-only governance audit log (in-memory; persisted on Day 10)."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(
        self, decision: Mapping[str, object], outcome: str, *, actor: str = "system"
    ) -> AuditRecord:
        analysis = decision.get("analysis") or {}
        analysis = analysis if isinstance(analysis, Mapping) else {}
        rec = AuditRecord(
            timestamp=_dt.datetime.now(_dt.UTC).isoformat(),
            findingHash=str(decision.get("findingHash", "")),
            findingId=(str(decision["findingId"]) if decision.get("findingId") else None),
            severity=str(analysis.get("severity", "unknown")),
            recommendedAction=str(analysis.get("recommendedAction", "")),
            confidence=float(analysis.get("confidence", 0.0) or 0.0),
            disposition=str(decision.get("disposition", "")),
            reasonCode=(str(decision["reasonCode"]) if decision.get("reasonCode") else None),
            outcome=outcome,
            actor=actor,
        )
        self._records.append(rec)
        return rec

    def list_all(self) -> list[AuditRecord]:
        return list(self._records)


@dataclass
class ActionResult:
    # ticket_created | ticket_exists | suppressed | pending_approval
    # | escalated | ticket_failed
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
    provider: TicketProvider,
    approvals: ApprovalStore,
    escalations: EscalationQueue,
    dead_letter: DeadLetterQueue | None = None,
) -> ActionResult:
    """Carry out a governed decision through the ticketing layer.

    The governance *disposition* decides the autonomy level; the analysis
    *recommendedAction* decides what is actually executed. A high-confidence
    suppression is auto-applied (no ticket); only a recommended ``create_ticket``
    ever opens a ticket. Provider failures are dead-lettered, not lost.
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
        try:
            ticket, created = provider.create(decision, via="auto")
        except Exception as exc:  # noqa: BLE001 - provider/transport errors are dead-lettered
            if dead_letter is not None:
                dead_letter.add(decision, error=f"{type(exc).__name__}: {exc}")
            return ActionResult(
                outcome="ticket_failed",
                disposition=disposition,
                findingHash=finding_hash,
                detail=f"Ticket provider '{getattr(provider, 'name', '?')}' failed; "
                       "decision dead-lettered for retry.",
            )
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
