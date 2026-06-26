"""Supervisor — the OS kernel that drives a run over the blueprint (PRODUCT_VISION §3-§6).

It compiles the blueprint into a concrete plan, then for each stage (in topological/gate
order): assembles each artifact's scoped inputs, runs the stage's artifacts in **parallel**
via the scheduler under the **budget governor**, has the cross-cutting **Critic + red-team**
review every artifact, then applies **eval-as-gate + the materiality dial** at the stage
gate. If a gate needs a human it **pauses durably** (sets ``AWAITING_APPROVAL`` and a
``pending_gate``) so the run can resume in a later request; on rejection it re-opens the
stage with the human's feedback, bounded by a max-iteration cap.

The supervisor is re-entrant: ``start`` runs from the first stage, ``resume`` continues
from a paused gate. Everything it does is written to the append-only audit trail.
"""

from __future__ import annotations

from typing import Any

from .agents import AgentContext, AgentRegistry, Reviewer
from .audit import AuditLog, ReasonCode
from .blueprint import ArtifactSpec, Blueprint, StageSpec
from .config import Settings
from .eval import aggregate_eval
from .gates import GateOutcome, evaluate_gate
from .gateway import Gateway
from .scheduler import Budget, BudgetExceededError, ParallelScheduler
from .skillpack import SkillPackRegistry
from .state import ArtifactRecord, ArtifactStatus, GateRecord, RunState, RunStatus
from .tools import ToolRegistry


class Supervisor:
    def __init__(
        self,
        *,
        blueprint: Blueprint,
        agents: AgentRegistry,
        skillpacks: SkillPackRegistry,
        settings: Settings,
        gateway: Gateway,
        audit: AuditLog,
        reviewer: Reviewer | None = None,
        scheduler: ParallelScheduler | None = None,
        tools_factory=None,  # callable(run) -> ToolRegistry
        tracer: Any = None,
    ) -> None:
        self.blueprint = blueprint
        self.agents = agents
        self.skillpacks = skillpacks
        self.settings = settings
        self.gateway = gateway
        self.audit = audit
        self.reviewer = reviewer or Reviewer()
        self.scheduler = scheduler or ParallelScheduler(
            max_concurrency=settings.max_concurrency, tracer=tracer
        )
        self._tools_factory = tools_factory
        self.tracer = tracer

    # --- planning -------------------------------------------------------------

    def compile_plan(self, run: RunState) -> RunState:
        """Compile the blueprint into a concrete, ordered plan on the blackboard."""
        plan = []
        for stage in self.blueprint.ordered_stages():
            plan.append({
                "stage": stage.key,
                "title": stage.title,
                "order": stage.order,
                "gateMode": stage.gate_mode or self.settings.default_gate_mode,
                "autoPass": stage.auto_pass,
                "artifacts": [
                    {"key": a.key, "title": a.title, "role": a.role} for a in stage.artifacts
                ],
            })
        run.plan = plan
        self.audit.append(
            run.run_id, ReasonCode.PLAN_COMPILED, stage=None,
            detail=f"Compiled {len(plan)} stages from blueprint "
                   f"{self.blueprint.name} v{self.blueprint.version}.",
            data={"stages": [p["stage"] for p in plan]},
        )
        return run

    # --- entry points ---------------------------------------------------------

    def start(self, run: RunState) -> RunState:
        run.status = RunStatus.RUNNING
        self.audit.append(run.run_id, ReasonCode.RUN_STARTED, detail="Run started.")
        if not run.plan:
            self.compile_plan(run)
        return self._drive(run, from_order=0)

    def resume(self, run: RunState, *, approved: bool, feedback: str = "") -> RunState:
        """Resume a paused run with a human's approve/reject decision."""
        if run.status != RunStatus.AWAITING_APPROVAL or not run.pending_gate:
            raise RuntimeError(f"run {run.run_id} is not awaiting approval")
        stage = self.blueprint.stage(run.pending_gate["stage"])
        gate = run.current_gate(stage.key)
        self.audit.append(run.run_id, ReasonCode.RUN_RESUMED, stage=stage.key, actor="human")

        if approved:
            if gate:
                gate.decision = "approved"
                gate.actor = "human"
                gate.feedback = feedback
            self._mark_stage_approved(run, stage)
            self.audit.append(
                run.run_id, ReasonCode.GATE_HUMAN_APPROVED, stage=stage.key, actor="human",
                detail=feedback or "Human approved the stage.",
            )
            run.pending_gate = None
            return self._drive(run, from_order=stage.order + 1)

        # Rejection -> bounded feedback loop: reopen the stage with the human's notes.
        if gate:
            gate.decision = "rejected"
            gate.actor = "human"
            gate.feedback = feedback
        run.feedback[stage.key] = feedback
        run.pending_gate = None
        rejections = sum(
            1 for g in run.gates if g.stage == stage.key and g.decision == "rejected"
        )
        self.audit.append(
            run.run_id, ReasonCode.GATE_HUMAN_REJECTED, stage=stage.key, actor="human",
            detail=feedback or "Human rejected the stage.",
            data={"rejections": rejections},
        )
        if rejections >= self.settings.max_stage_iterations:
            run.status = RunStatus.REJECTED
            run.errors.append(
                f"stage {stage.key} rejected {rejections}x (>= max "
                f"{self.settings.max_stage_iterations}); halting."
            )
            run.touch()
            return run
        self.audit.append(
            run.run_id, ReasonCode.STAGE_REOPENED, stage=stage.key,
            detail=f"Re-opening {stage.key} with feedback (iteration {rejections + 1}).",
        )
        return self._drive(run, from_order=stage.order)

    # --- core loop ------------------------------------------------------------

    def _drive(self, run: RunState, *, from_order: int) -> RunState:
        run.status = RunStatus.RUNNING
        for stage in self.blueprint.ordered_stages():
            if stage.order < from_order:
                continue
            run.current_stage = stage.key
            self.audit.append(run.run_id, ReasonCode.STAGE_STARTED, stage=stage.key)

            try:
                self._execute_stage(run, stage)
            except BudgetExceededError as exc:
                run.status = RunStatus.BUDGET_EXCEEDED
                run.errors.append(str(exc))
                self.audit.append(
                    run.run_id, ReasonCode.BUDGET_EXCEEDED, stage=stage.key, detail=str(exc),
                )
                run.touch()
                return run

            gate = self._gate_stage(run, stage)
            run.gates.append(gate)
            if gate.decision == "awaiting_human":
                run.status = RunStatus.AWAITING_APPROVAL
                run.pending_gate = {
                    "stage": stage.key,
                    "title": stage.title,
                    "evalScore": gate.eval_score,
                    "qualityBar": gate.quality_bar,
                    "mode": gate.mode,
                    "artifacts": list(stage.artifact_keys()),
                }
                self.audit.append(
                    run.run_id, ReasonCode.GATE_AWAITING_HUMAN, stage=stage.key,
                    detail=f"Gate awaiting human (eval {gate.eval_score}).",
                )
                run.touch()
                return run

            # auto-approved
            self._mark_stage_approved(run, stage)
            self.audit.append(
                run.run_id, ReasonCode.GATE_AUTO_APPROVED, stage=stage.key,
                detail=f"Auto-approved (eval {gate.eval_score} vs bar {gate.quality_bar}).",
            )

        run.status = RunStatus.COMPLETED
        run.current_stage = None
        self.audit.append(
            run.run_id, ReasonCode.RUN_COMPLETED,
            detail=f"Run completed; cost ${run.cost_usd:.4f}, {len(run.artifacts)} artifacts.",
            data={"costUsd": run.cost_usd, "artifacts": sorted(run.artifacts)},
        )
        run.touch()
        return run

    # --- stage execution ------------------------------------------------------

    def _execute_stage(self, run: RunState, stage: StageSpec) -> None:
        budget = Budget(
            max_usd=self.settings.budget_usd,
            max_wall_seconds=self.settings.budget_wall_seconds,
            spent_usd=run.cost_usd,
        )

        if stage.auto_pass:
            for spec in stage.artifacts:
                self._auto_pass_artifact(run, spec)
            return

        tools = self._tools_factory(run) if self._tools_factory else ToolRegistry(
            run.workspace_dir or self.settings.workspace
        )

        def execute(spec: ArtifactSpec) -> Any:
            return self._produce_artifact(run, spec, tools, budget)

        stage_run = self.scheduler.run_stage(
            stage.key, stage.artifacts, execute, budget=budget
        )
        # Persist accounting + reviews onto the blackboard (after the parallel section).
        for spec in stage.artifacts:
            result = stage_run.results[spec.key]
            self._record_artifact(run, spec, result)

        self.audit.append(
            run.run_id, ReasonCode.STAGE_COMPLETED, stage=stage.key,
            detail=f"Produced {len(stage.artifacts)} artifacts; "
                   f"max parallelism {stage_run.max_parallelism}.",
            data={"waves": stage_run.waves, "maxParallelism": stage_run.max_parallelism},
        )

    def _produce_artifact(self, run, spec, tools, budget):
        budget.check()
        agent = self.agents.resolve(spec.role)
        pack = self.skillpacks.get(spec.skillpack or spec.role)
        ctx = AgentContext(
            spec=spec, run=run, settings=self.settings, gateway=self.gateway,
            tools=tools, skillpack=pack, tracer=self.tracer,
            inputs=self._scoped_inputs(run, spec),
        )
        span_cm = (
            self.tracer.start_span("agent.run", role=spec.role, artifact=spec.key)
            if self.tracer is not None else _null()
        )
        with span_cm:
            result = agent.run(ctx)
        budget.charge(result.cost_usd)
        return result

    def _scoped_inputs(self, run: RunState, spec: ArtifactSpec) -> dict[str, ArtifactRecord]:
        """Only artifacts on incoming edges (depends_on + informs) — context scoping."""
        keys = set(spec.depends_on) | set(spec.informs)
        return {k: run.artifacts[k] for k in keys if k in run.artifacts}

    def _record_artifact(self, run: RunState, spec: ArtifactSpec, result) -> None:
        existing = run.artifacts.get(spec.key)
        iterations = (existing.iterations + 1) if existing else 1
        record = ArtifactRecord(
            key=spec.key, title=spec.title, stage=spec.stage, role=spec.role,
            status=ArtifactStatus.PRODUCED, content=result.content, path=result.path,
            citations=result.citations, cost_usd=result.cost_usd, tokens=result.tokens,
            iterations=iterations,
            served_provider=result.served_provider, served_model=result.served_model,
        )
        run.artifacts[spec.key] = record
        run.add_cost(result.cost_usd, result.tokens)
        self.audit.append(
            run.run_id, ReasonCode.ARTIFACT_PRODUCED, stage=spec.stage, artifact=spec.key,
            actor=spec.role, detail=result.notes or f"Produced {spec.title}.",
            data={"path": result.path, "costUsd": result.cost_usd},
        )

        # Cross-cutting review: Critic + red-team (mandatory, every artifact).
        review = self.reviewer.review(spec, record)
        record.critic_score = review.critic_score
        record.redteam_findings = review.redteam_findings
        record.eval_score = review.eval_score
        record.status = ArtifactStatus.REVIEWED
        self.audit.append(
            run.run_id, ReasonCode.CRITIC_SCORED, stage=spec.stage, artifact=spec.key,
            actor="critic", detail=f"Critic {review.critic_score} -> eval {review.eval_score}.",
            data={"criticScore": review.critic_score, "evalScore": review.eval_score},
        )
        if review.redteam_findings:
            self.audit.append(
                run.run_id, ReasonCode.REDTEAM_FLAGGED, stage=spec.stage, artifact=spec.key,
                actor="red-team", detail="; ".join(review.redteam_findings[:5]),
                data={"findings": review.redteam_findings},
            )

    def _auto_pass_artifact(self, run: RunState, spec: ArtifactSpec) -> None:
        record = ArtifactRecord(
            key=spec.key, title=spec.title, stage=spec.stage, role=spec.role,
            status=ArtifactStatus.AUTO_PASSED,
            content={"placeholder": True, "note": f"{spec.title} stubbed (auto-pass)."},
            eval_score=1.0, critic_score=1.0,
        )
        run.artifacts[spec.key] = record
        self.audit.append(
            run.run_id, ReasonCode.ARTIFACT_PRODUCED, stage=spec.stage, artifact=spec.key,
            detail=f"Auto-pass placeholder for {spec.title}.",
        )

    # --- gating ---------------------------------------------------------------

    def _gate_stage(self, run: RunState, stage: StageSpec) -> GateRecord:
        scores = [
            run.artifacts[a.key].eval_score
            for a in stage.artifacts
            if a.key in run.artifacts and run.artifacts[a.key].eval_score is not None
        ]
        eval_score = aggregate_eval(scores)
        quality_bar = (
            stage.quality_bar if stage.quality_bar is not None
            else self.settings.eval_quality_bar
        )
        mode = stage.gate_mode or self.settings.default_gate_mode

        # Stub stages always auto-pass regardless of mode (they have no real artifacts).
        if stage.auto_pass:
            self.audit.append(
                run.run_id, ReasonCode.EVAL_GATE_PASS, stage=stage.key,
                detail="Stub stage auto-passed.",
            )
            return GateRecord(
                stage=stage.key, mode=mode, eval_score=1.0, quality_bar=quality_bar,
                passed_eval=True, decision="auto_approved", actor="system",
            )

        decision = evaluate_gate(mode=mode, eval_score=eval_score, quality_bar=quality_bar)
        self.audit.append(
            run.run_id,
            ReasonCode.EVAL_GATE_PASS if decision.passed_eval else ReasonCode.EVAL_GATE_FAIL,
            stage=stage.key,
            detail=decision.reason,
            data={"evalScore": eval_score, "qualityBar": quality_bar},
        )
        return GateRecord(
            stage=stage.key, mode=mode, eval_score=eval_score, quality_bar=quality_bar,
            passed_eval=decision.passed_eval,
            decision=(
                "auto_approved" if decision.outcome == GateOutcome.AUTO_APPROVED
                else "awaiting_human"
            ),
            actor="system",
        )

    def _mark_stage_approved(self, run: RunState, stage: StageSpec) -> None:
        for spec in stage.artifacts:
            record = run.artifacts.get(spec.key)
            if record and record.status != ArtifactStatus.AUTO_PASSED:
                record.status = ArtifactStatus.APPROVED


class _null:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False
