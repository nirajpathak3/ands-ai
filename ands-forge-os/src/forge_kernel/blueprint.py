"""Blueprint — the program the kernel executes, as swappable DATA.

A Blueprint is a declarative DAG: **stages** (ordered, gated groups) each containing
**artifacts** (the atomic units of work, one owning agent role + a quality bar). This is
the executable form of the lifecycle diagram's legend:

* **solid edge = gate (must precede)** -> a stage opens only after the previous stage's
  gate is approved; an artifact may also declare intra-stage ``depends_on`` predecessors.
* **dotted edge = informs (non-blocking context)** -> ``informs`` edges carry context
  from an upstream artifact without blocking (the "shift-left" parallelism).

The kernel knows ONLY this schema. Product-development specifics (which stages, which
artifacts, which roles) live entirely in the blueprint file loaded by ``forge_os`` — so
the same kernel runs any project by loading a different blueprint.

Stdlib-only dataclasses; YAML/JSON loading imports its parser lazily.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BlueprintError(ValueError):
    """The blueprint is structurally invalid (dangling edge, cycle, bad gate mode)."""


@dataclass(frozen=True)
class ArtifactSpec:
    """One artifact node: an agent role produces it, a rubric judges it."""

    key: str
    title: str
    role: str  # owning agent role (resolved against the agent registry)
    stage: str  # owning stage key (filled in by the loader)
    depends_on: tuple[str, ...] = ()  # intra-DAG gate predecessors (artifact keys)
    informs: tuple[str, ...] = ()  # non-blocking context edges (artifact keys)
    quality_bar: float = 0.75  # eval-as-gate threshold for this artifact
    rubric: tuple[str, ...] = ()  # named criteria the Critic scores against
    skillpack: str | None = None  # skill-pack id (data) the agent loads
    auto_pass: bool = False  # stub artifacts (auto-pass placeholder)
    model: str | None = None  # pin a specific model (overrides task/stage tiering)
    params: Mapping[str, Any] = field(default_factory=dict)  # agent params (e.g. tool)


@dataclass(frozen=True)
class StageSpec:
    """One lifecycle stage: a gated group of artifacts run in parallel."""

    key: str
    title: str
    order: int
    artifacts: tuple[ArtifactSpec, ...]
    gate_mode: str | None = None  # materiality; None -> settings.default_gate_mode
    quality_bar: float | None = None  # stage gate bar; None -> settings.eval_quality_bar
    auto_pass: bool = False  # stub stage (Security/Analytics/Ops in the MVP slice)
    description: str = ""

    def artifact_keys(self) -> tuple[str, ...]:
        return tuple(a.key for a in self.artifacts)


@dataclass(frozen=True)
class Blueprint:
    name: str
    version: str
    stages: tuple[StageSpec, ...]
    description: str = ""

    # --- lookups --------------------------------------------------------------

    def ordered_stages(self) -> list[StageSpec]:
        return sorted(self.stages, key=lambda s: s.order)

    def stage(self, key: str) -> StageSpec:
        for s in self.stages:
            if s.key == key:
                return s
        raise KeyError(key)

    def artifacts(self) -> list[ArtifactSpec]:
        return [a for s in self.ordered_stages() for a in s.artifacts]

    def artifact(self, key: str) -> ArtifactSpec:
        for a in self.artifacts():
            if a.key == key:
                return a
        raise KeyError(key)

    # --- validation -----------------------------------------------------------

    def validate(self) -> None:
        """Reject dangling edges, duplicate keys, bad gate modes, and cycles."""
        from .config import GATE_MODES

        artifact_keys = [a.key for a in self.artifacts()]
        dupes = {k for k in artifact_keys if artifact_keys.count(k) > 1}
        if dupes:
            raise BlueprintError(f"duplicate artifact keys: {sorted(dupes)}")
        known = set(artifact_keys)

        for stage in self.stages:
            if stage.gate_mode is not None and stage.gate_mode not in GATE_MODES:
                raise BlueprintError(
                    f"stage {stage.key!r}: invalid gate_mode {stage.gate_mode!r} "
                    f"(expected one of {GATE_MODES})"
                )
            for art in stage.artifacts:
                for edge_name in ("depends_on", "informs"):
                    for ref in getattr(art, edge_name):
                        if ref not in known:
                            raise BlueprintError(
                                f"artifact {art.key!r}: {edge_name} references unknown "
                                f"artifact {ref!r}"
                            )

        self._detect_cycles()

    def _detect_cycles(self) -> None:
        """Cycle detection over the combined gate-edge graph (depends_on)."""
        graph = {a.key: set(a.depends_on) for a in self.artifacts()}
        state: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=done

        def visit(node: str, path: list[str]) -> None:
            if state.get(node) == 2:
                return
            if state.get(node) == 1:
                cycle = " -> ".join([*path, node])
                raise BlueprintError(f"dependency cycle: {cycle}")
            state[node] = 1
            for dep in graph.get(node, ()):  # noqa: SIM118
                visit(dep, [*path, node])
            state[node] = 2

        for key in graph:
            visit(key, [])


# --- loading ------------------------------------------------------------------


def from_dict(data: Mapping[str, Any]) -> Blueprint:
    """Build a Blueprint from a parsed mapping (YAML/JSON-agnostic)."""
    stages: list[StageSpec] = []
    raw_stages = data.get("stages") or []
    for idx, raw in enumerate(raw_stages):
        stage_key = raw["key"]
        artifacts = tuple(
            _artifact_from_dict(
                raw_art, stage_key, stage_auto_pass=raw.get("auto_pass", False),
                stage_model=raw.get("model"),
            )
            for raw_art in (raw.get("artifacts") or [])
        )
        stages.append(
            StageSpec(
                key=stage_key,
                title=raw.get("title", stage_key),
                order=int(raw.get("order", idx)),
                artifacts=artifacts,
                gate_mode=raw.get("gate_mode"),
                quality_bar=raw.get("quality_bar"),
                auto_pass=bool(raw.get("auto_pass", False)),
                description=raw.get("description", ""),
            )
        )
    bp = Blueprint(
        name=data.get("name", "unnamed"),
        version=str(data.get("version", "0")),
        description=data.get("description", ""),
        stages=tuple(stages),
    )
    bp.validate()
    return bp


def _artifact_from_dict(
    raw: Mapping[str, Any], stage_key: str, *, stage_auto_pass: bool,
    stage_model: str | None = None,
) -> ArtifactSpec:
    return ArtifactSpec(
        key=raw["key"],
        title=raw.get("title", raw["key"]),
        role=raw.get("role", raw["key"]),
        stage=stage_key,
        depends_on=_as_tuple(raw.get("depends_on")),
        informs=_as_tuple(raw.get("informs")),
        quality_bar=float(raw.get("quality_bar", 0.75)),
        rubric=_as_tuple(raw.get("rubric")),
        skillpack=raw.get("skillpack"),
        auto_pass=bool(raw.get("auto_pass", stage_auto_pass)),
        model=raw.get("model", stage_model),  # artifact-level wins, else stage-level
        params=dict(raw.get("params") or {}),
    )


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(v) for v in value)
    return ()


def load_blueprint(path: str | Path) -> Blueprint:
    """Load a blueprint from a YAML or JSON file (parser imported lazily)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # lazy: kernel imports without pyyaml

        data = yaml.safe_load(text)
    else:
        import json

        data = json.loads(text)
    return from_dict(data)
