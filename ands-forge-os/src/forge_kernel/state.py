"""RunState — the blackboard (durable run state, PRODUCT_VISION §3).

A single, serializable record of everything about one run: the vision, the compiled plan,
each produced artifact (content + review scores + cost + citations), every gate decision,
the running cost/token totals, and the run status. The supervisor and scheduler read and
write this blackboard; the durable ``RunStore`` persists it so a run can pause at a HITL
gate and resume in a later request (across sessions, by ``run_id``).

Stdlib dataclasses with explicit ``to_dict``/``from_dict`` so the store can serialize to
JSON without any third-party dependency.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"


class ArtifactStatus(StrEnum):
    PENDING = "pending"
    PRODUCED = "produced"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_PASSED = "auto_passed"


@dataclass
class ArtifactRecord:
    key: str
    title: str
    stage: str
    role: str
    status: str = ArtifactStatus.PENDING
    content: dict[str, Any] = field(default_factory=dict)
    path: str | None = None  # filesystem path, if written by a tool
    critic_score: float | None = None
    redteam_findings: list[str] = field(default_factory=list)
    eval_score: float | None = None
    cost_usd: float = 0.0
    tokens: int = 0
    iterations: int = 0
    citations: list[dict[str, Any]] = field(default_factory=list)
    # The provider/model that actually served this artifact (reflects gateway fallback).
    served_provider: str | None = None
    served_model: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key, "title": self.title, "stage": self.stage, "role": self.role,
            "status": str(self.status), "content": self.content, "path": self.path,
            "criticScore": self.critic_score, "redteamFindings": self.redteam_findings,
            "evalScore": self.eval_score, "costUsd": self.cost_usd, "tokens": self.tokens,
            "iterations": self.iterations, "citations": self.citations,
            "servedProvider": self.served_provider, "servedModel": self.served_model,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ArtifactRecord:
        return cls(
            key=d["key"], title=d["title"], stage=d["stage"], role=d["role"],
            status=d.get("status", ArtifactStatus.PENDING), content=d.get("content", {}),
            path=d.get("path"), critic_score=d.get("criticScore"),
            redteam_findings=d.get("redteamFindings", []), eval_score=d.get("evalScore"),
            cost_usd=d.get("costUsd", 0.0), tokens=d.get("tokens", 0),
            iterations=d.get("iterations", 0), citations=d.get("citations", []),
            served_provider=d.get("servedProvider"), served_model=d.get("servedModel"),
        )


@dataclass
class GateRecord:
    """One stage-gate decision (materiality dial + eval-as-gate)."""

    stage: str
    mode: str
    eval_score: float | None = None
    quality_bar: float | None = None
    passed_eval: bool | None = None
    decision: str = "pending"  # auto_approved | awaiting_human | approved | rejected
    actor: str = "system"
    feedback: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage, "mode": self.mode, "evalScore": self.eval_score,
            "qualityBar": self.quality_bar, "passedEval": self.passed_eval,
            "decision": self.decision, "actor": self.actor, "feedback": self.feedback,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GateRecord:
        return cls(
            stage=d["stage"], mode=d["mode"], eval_score=d.get("evalScore"),
            quality_bar=d.get("qualityBar"), passed_eval=d.get("passedEval"),
            decision=d.get("decision", "pending"), actor=d.get("actor", "system"),
            feedback=d.get("feedback", ""), timestamp=d.get("timestamp", _now()),
        )


@dataclass
class RunState:
    run_id: str
    blueprint_name: str
    blueprint_version: str
    vision: str = ""
    vision_brief: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    status: str = RunStatus.PENDING
    current_stage: str | None = None
    artifacts: dict[str, ArtifactRecord] = field(default_factory=dict)
    gates: list[GateRecord] = field(default_factory=list)
    cost_usd: float = 0.0
    tokens: int = 0
    workspace_dir: str | None = None
    # When paused for a human, this holds what the gate is asking (for resume).
    pending_gate: dict[str, Any] | None = None
    # Human feedback on a rejected stage, keyed by stage — fed back to agents on re-run.
    feedback: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def new(cls, blueprint_name: str, blueprint_version: str, *, vision: str) -> RunState:
        return cls(
            run_id=uuid.uuid4().hex,
            blueprint_name=blueprint_name,
            blueprint_version=blueprint_version,
            vision=vision,
        )

    def touch(self) -> None:
        self.updated_at = _now()

    def add_cost(self, cost_usd: float, tokens: int) -> None:
        self.cost_usd = round(self.cost_usd + cost_usd, 6)
        self.tokens += tokens

    def current_gate(self, stage: str) -> GateRecord | None:
        for gate in reversed(self.gates):
            if gate.stage == stage:
                return gate
        return None

    def to_dict(self) -> dict:
        return {
            "runId": self.run_id,
            "blueprintName": self.blueprint_name,
            "blueprintVersion": self.blueprint_version,
            "vision": self.vision,
            "visionBrief": self.vision_brief,
            "plan": self.plan,
            "status": str(self.status),
            "currentStage": self.current_stage,
            "artifacts": {k: a.to_dict() for k, a in self.artifacts.items()},
            "gates": [g.to_dict() for g in self.gates],
            "costUsd": self.cost_usd,
            "tokens": self.tokens,
            "workspaceDir": self.workspace_dir,
            "pendingGate": self.pending_gate,
            "feedback": self.feedback,
            "errors": self.errors,
            "startedAt": self.started_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RunState:
        state = cls(
            run_id=d["runId"],
            blueprint_name=d["blueprintName"],
            blueprint_version=d["blueprintVersion"],
            vision=d.get("vision", ""),
            vision_brief=d.get("visionBrief"),
            plan=d.get("plan", []),
            status=d.get("status", RunStatus.PENDING),
            current_stage=d.get("currentStage"),
            cost_usd=d.get("costUsd", 0.0),
            tokens=d.get("tokens", 0),
            workspace_dir=d.get("workspaceDir"),
            pending_gate=d.get("pendingGate"),
            feedback=d.get("feedback", {}),
            errors=d.get("errors", []),
            started_at=d.get("startedAt", _now()),
            updated_at=d.get("updatedAt", _now()),
        )
        state.artifacts = {
            k: ArtifactRecord.from_dict(v) for k, v in (d.get("artifacts") or {}).items()
        }
        state.gates = [GateRecord.from_dict(g) for g in (d.get("gates") or [])]
        return state
