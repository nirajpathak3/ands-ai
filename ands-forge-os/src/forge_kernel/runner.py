"""Forge — the high-level engine + durable RunStore (the walking-skeleton runtime).

``Forge`` wires the kernel together (AI Gateway, audit, supervisor, scheduler, tools) and
exposes the run lifecycle: ``start(vision)`` runs autonomously until it completes or pauses
at a HITL gate; ``resume(run_id, approved, feedback)`` continues a paused run. The
``RunStore`` persists each run's blackboard + audit trail to disk so a run can pause in one
request/session and resume in another (keyed by ``run_id``) — durable HITL without
requiring LangGraph for the skeleton. (The compiled-graph runner is a later seam.)

Offline-deterministic by default: no keys, $0, reproducible.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .agents import AgentRegistry, Reviewer
from .agents.reviewer import Judge
from .audit import AuditLog
from .blueprint import Blueprint
from .config import Settings, get_settings
from .gateway.factory import build_gateway
from .observability.tracing import Tracer, build_otel_exporter
from .scheduler import ParallelScheduler
from .skillpack import SkillPackRegistry
from .state import RunState, RunStatus
from .supervisor import Supervisor
from .tools import default_tools


class RunStore:
    """Durable per-run state + audit trail on the filesystem (JSON)."""

    def __init__(self, base: str | Path) -> None:
        self.base = Path(base)

    def run_dir(self, run_id: str) -> Path:
        return self.base / "runs" / run_id

    def artifacts_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "artifacts"

    def save(self, run: RunState, audit_events: list[dict]) -> None:
        d = self.run_dir(run.run_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "run.json").write_text(
            json.dumps(run.to_dict(), indent=2), encoding="utf-8"
        )
        (d / "audit.json").write_text(
            json.dumps(audit_events, indent=2), encoding="utf-8"
        )

    def load(self, run_id: str) -> tuple[RunState, list[dict]]:
        d = self.run_dir(run_id)
        state = RunState.from_dict(json.loads((d / "run.json").read_text(encoding="utf-8")))
        audit_path = d / "audit.json"
        events = (
            json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else []
        )
        return state, events

    def exists(self, run_id: str) -> bool:
        return (self.run_dir(run_id) / "run.json").exists()

    def list_runs(self) -> list[str]:
        root = self.base / "runs"
        if not root.exists():
            return []
        return sorted(p.name for p in root.iterdir() if (p / "run.json").exists())


class Forge:
    def __init__(
        self,
        *,
        blueprint: Blueprint,
        agents: AgentRegistry,
        skillpacks: SkillPackRegistry | None = None,
        settings: Settings | None = None,
        store: RunStore | None = None,
        reviewer: Reviewer | None = None,
        judge_factory: Callable[[Any, Settings], Judge] | None = None,
    ) -> None:
        self.blueprint = blueprint
        self.agents = agents
        self.skillpacks = skillpacks or SkillPackRegistry()
        self.settings = settings or get_settings()
        self.store = store or RunStore(self.settings.workspace)
        self.tracer = Tracer(otel_export=build_otel_exporter(self.settings))
        self.audit = AuditLog()
        self.gateway = build_gateway(self.settings, tracer=self.tracer)
        if reviewer is None:
            # The program may supply an LLM-as-judge; built here because it needs the
            # gateway. Offline the judge is a no-op, so this stays deterministic.
            judge = judge_factory(self.gateway, self.settings) if judge_factory else None
            reviewer = Reviewer(judge=judge)
        self.supervisor = Supervisor(
            blueprint=self.blueprint,
            agents=self.agents,
            skillpacks=self.skillpacks,
            settings=self.settings,
            gateway=self.gateway,
            audit=self.audit,
            reviewer=reviewer,
            scheduler=ParallelScheduler(
                max_concurrency=self.settings.max_concurrency, tracer=self.tracer
            ),
            tools_factory=self._tools_factory,
            tracer=self.tracer,
        )

    def _tools_factory(self, run: RunState):
        return default_tools(run.workspace_dir or self.store.artifacts_dir(run.run_id))

    # --- lifecycle ------------------------------------------------------------

    def start(self, vision: str) -> RunState:
        run = RunState.new(self.blueprint.name, self.blueprint.version, vision=vision)
        run.workspace_dir = str(self.store.artifacts_dir(run.run_id))
        result = self.supervisor.start(run)
        self._persist(result)
        return result

    def resume(self, run_id: str, *, approved: bool, feedback: str = "") -> RunState:
        run = self._load_into_audit(run_id)
        result = self.supervisor.resume(run, approved=approved, feedback=feedback)
        self._persist(result)
        return result

    def get(self, run_id: str) -> RunState:
        if self.store.exists(run_id):
            state, _ = self.store.load(run_id)
            return state
        raise KeyError(run_id)

    def audit_for(self, run_id: str) -> list[dict]:
        if self.store.exists(run_id):
            _, events = self.store.load(run_id)
            return events
        return self.audit.to_list(run_id)

    def is_awaiting(self, run_id: str) -> bool:
        return self.get(run_id).status == RunStatus.AWAITING_APPROVAL

    # --- internals ------------------------------------------------------------

    def _persist(self, run: RunState) -> None:
        self.store.save(run, self.audit.to_list(run.run_id))

    def _load_into_audit(self, run_id: str) -> RunState:
        state, events = self.store.load(run_id)
        # Re-seed only this run's prior events if the in-memory log doesn't have them yet
        # (fresh process / new Forge instance), keeping the trail continuous.
        if not self.audit.events(run_id):
            self.audit.extend(events)
        return state

    def status_summary(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        return {
            "runId": run.run_id,
            "status": str(run.status),
            "currentStage": run.current_stage,
            "costUsd": run.cost_usd,
            "artifacts": {k: a.status for k, a in run.artifacts.items()},
            "pendingGate": run.pending_gate,
        }
