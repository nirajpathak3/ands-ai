"""Append-only audit trail — the kernel's accountability backbone.

Every meaningful decision (an agent produced an artifact, a critic/red-team scored it,
an eval gate passed/failed, a human approved/rejected, the budget governor paused a run)
is written here as an immutable event with a machine-readable ``reasonCode``. The audit
log is the source of truth that answers *"why did Forge do this?"* for every step of a
run — the governed-automation story ported from ``ai-secops-copilot``, generalized from
security findings to lifecycle artifacts.

Stdlib only; in-memory by default (a durable backend slots behind the same ``append``).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ReasonCode(StrEnum):
    """Machine-readable rationale for an audit event."""

    # Run lifecycle
    RUN_STARTED = "run_started"
    PLAN_COMPILED = "plan_compiled"
    RUN_COMPLETED = "run_completed"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"

    # Stage / agent execution
    STAGE_STARTED = "stage_started"
    ARTIFACT_PRODUCED = "artifact_produced"
    STAGE_COMPLETED = "stage_completed"
    STAGE_REOPENED = "stage_reopened"  # bounded feedback loop on rejection

    # Review (cross-cutting Critic + red-team)
    CRITIC_SCORED = "critic_scored"
    REDTEAM_FLAGGED = "redteam_flagged"

    # Gates
    EVAL_GATE_PASS = "eval_gate_pass"
    EVAL_GATE_FAIL = "eval_gate_fail"
    GATE_AUTO_APPROVED = "gate_auto_approved"
    GATE_AWAITING_HUMAN = "gate_awaiting_human"
    GATE_HUMAN_APPROVED = "gate_human_approved"
    GATE_HUMAN_REJECTED = "gate_human_rejected"

    # Governor
    BUDGET_OK = "budget_ok"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Tools
    TOOL_INVOKED = "tool_invoked"


@dataclass(frozen=True)
class AuditEvent:
    """One immutable audit event."""

    timestamp: str
    run_id: str
    reason_code: str
    actor: str  # "system" (autonomous) | "human" | role name (e.g. "critic")
    stage: str | None = None
    artifact: str | None = None
    detail: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLog:
    """Append-only audit trail (in-memory; durable backend behind the same seam)."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(
        self,
        run_id: str,
        reason_code: ReasonCode | str,
        *,
        actor: str = "system",
        stage: str | None = None,
        artifact: str | None = None,
        detail: str = "",
        data: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            timestamp=_dt.datetime.now(_dt.UTC).isoformat(),
            run_id=run_id,
            reason_code=str(reason_code),
            actor=actor,
            stage=stage,
            artifact=artifact,
            detail=detail,
            data=dict(data or {}),
        )
        self._events.append(event)
        return event

    def extend(self, events: list[Mapping[str, Any]]) -> None:
        """Re-seed previously persisted events (keeps the trail continuous on resume)."""
        for e in events:
            self._events.append(
                AuditEvent(
                    timestamp=e.get("timestamp", _dt.datetime.now(_dt.UTC).isoformat()),
                    run_id=e["run_id"],
                    reason_code=e["reason_code"],
                    actor=e.get("actor", "system"),
                    stage=e.get("stage"),
                    artifact=e.get("artifact"),
                    detail=e.get("detail", ""),
                    data=dict(e.get("data") or {}),
                )
            )

    def events(self, run_id: str | None = None) -> list[AuditEvent]:
        if run_id is None:
            return list(self._events)
        return [e for e in self._events if e.run_id == run_id]

    def to_list(self, run_id: str | None = None) -> list[dict]:
        return [e.to_dict() for e in self.events(run_id)]

    def clear(self) -> None:
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)
