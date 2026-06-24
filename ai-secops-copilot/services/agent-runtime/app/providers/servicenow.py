"""ServiceNow mock ticket adapter (ADR-003: ServiceNow is mocked for the MVP).

Implements the same ``TicketProvider`` contract as the real Jira adapter, so the
"provider-agnostic action layer" story is proven end-to-end without a second live
tenant. It mimics ServiceNow incident-table semantics (a ``sys_id`` plus a human
``INC...`` number) and is idempotent on ``findingHash`` (ADR-009).

Swapping this for a live ServiceNow tenant later means implementing the same three
methods against the Table API — no change to the orchestration/pipeline code.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Mapping

from ..ticketing import Ticket

# ServiceNow impact/urgency-style mapping from our severity scale (illustrative).
_SEVERITY_TO_PRIORITY = {
    "critical": "1 - Critical",
    "high": "2 - High",
    "medium": "3 - Moderate",
    "low": "4 - Low",
    "info": "5 - Planning",
}

# Lifecycle status -> ServiceNow incident state (illustrative).
_STATUS_TO_STATE = {
    "open": "New",
    "in_progress": "In Progress",
    "resolved": "Resolved",
    "closed": "Closed",
    "done": "Closed",
}


class ServiceNowTicketProvider:
    """In-memory ServiceNow stand-in with incident-table-like records."""

    name = "servicenow"

    def __init__(self, prefix: str = "INC") -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)
        self._by_hash: dict[str, Ticket] = {}
        self.records: dict[str, dict] = {}  # sys_id -> raw incident (inspectable)

    def create(self, decision: Mapping[str, object], *, via: str = "auto") -> tuple[Ticket, bool]:
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
        number = f"{self._prefix}{next(self._counter):07d}"
        sys_id = uuid.uuid4().hex
        summary = f"[{severity.upper()}] {finding_id}: security finding requires remediation"

        self.records[sys_id] = {
            "sys_id": sys_id,
            "number": number,
            "short_description": summary,
            "priority": _SEVERITY_TO_PRIORITY.get(severity, "5 - Planning"),
            "correlation_id": finding_hash,  # ServiceNow's natural idempotency anchor
            "state": "New",
        }
        ticket = Ticket(
            key=number,
            findingId=str(finding_id) if finding_id is not None else None,
            findingHash=finding_hash,
            severity=severity,
            summary=summary,
            createdVia=via,
            provider=self.name,
        )
        self._by_hash[finding_hash] = ticket
        return ticket, True

    def get(self, finding_hash: str) -> Ticket | None:
        return self._by_hash.get(finding_hash)

    def all(self) -> list[Ticket]:
        return list(self._by_hash.values())

    def transition(self, finding_hash: str, status: str) -> Ticket | None:
        """Apply a lifecycle status, mirroring it onto the incident record state."""
        ticket = self._by_hash.get(finding_hash)
        if ticket is None:
            return None
        ticket.apply_status(status)
        # Reflect onto the incident-table-like record (illustrative state mapping).
        for record in self.records.values():
            if record.get("correlation_id") == finding_hash:
                record["state"] = _STATUS_TO_STATE.get(status, "In Progress")
        return ticket
