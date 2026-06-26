"""The Agent port + execution context.

Every worker agent implements ``run(ctx) -> AgentResult``: it reads the blackboard and
its upstream inputs (artifacts on incoming DAG edges only — context scoping keeps the
prompt small, PRODUCT_VISION §15), optionally calls the AI Gateway and tools, and returns
a structured artifact payload plus cost/citations. The kernel handles scheduling, review,
gating, audit, and persistence around it.

The "Reasoner/Thinker" loop (reason -> plan -> act -> reflect) from PRODUCT_VISION §4 is a
discipline inside ``run``; offline stub agents synthesize deterministically from the
blackboard, real agents drive it through the Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid hard imports so the port stays light
    from ..blueprint import ArtifactSpec
    from ..config import Settings
    from ..gateway import Gateway
    from ..skillpack import SkillPack
    from ..state import ArtifactRecord, RunState
    from ..tools import ToolRegistry


@dataclass
class AgentContext:
    """Everything an agent needs, assembled by the scheduler per artifact."""

    spec: ArtifactSpec
    run: RunState
    settings: Settings
    gateway: Gateway
    tools: ToolRegistry
    skillpack: SkillPack | None = None
    tracer: Any = None
    # Upstream artifacts on this artifact's incoming edges (depends_on + informs), so the
    # agent only sees the context it is entitled to — not the entire blackboard.
    inputs: dict[str, ArtifactRecord] = field(default_factory=dict)


@dataclass
class AgentResult:
    """What an agent returns: the structured artifact payload + accounting."""

    content: dict[str, Any]
    citations: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    tokens: int = 0
    notes: str = ""
    # Optional filesystem path if the agent wrote an artifact via a tool.
    path: str | None = None
    # The provider/model that actually served the content (reflects gateway fallback, e.g.
    # gemini -> groq on a 429). None offline / when no LLM call was made.
    served_provider: str | None = None
    served_model: str | None = None


@runtime_checkable
class Agent(Protocol):
    role: str

    def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover - protocol
        ...
