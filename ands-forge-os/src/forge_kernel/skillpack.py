"""SkillPack — a per-role, versioned, trainable capability bundle (PRODUCT_VISION §7).

A skill pack makes an agent role better/domain-specialized **without changing the
kernel**: it carries the role's policy (system prompt + guardrails), few-shot exemplars,
retrieval corpus references, an output contract, the allowed tools, and an eval rubric
with a quality bar. "Training" = author -> evaluate (LLM-as-judge vs rubric) -> version
-> hot-load. The same kernel produces a fintech PRD or a healthcare PRD by swapping packs.

In the offline walking skeleton, deterministic stub agents read a pack's ``policy`` and
``rubric`` but synthesize content from the blackboard; real skill-pack-driven agents
(later build step) consume ``exemplars``/``corpus`` through the AI Gateway. Stdlib only;
YAML/JSON loaded lazily.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillPack:
    role: str
    version: str = "0"
    policy: str = ""  # system prompt + guardrails
    exemplars: tuple[Mapping[str, Any], ...] = ()  # few-shot gold artifacts
    corpus: tuple[str, ...] = ()  # retrieval source references (RAG)
    output_schema: Mapping[str, Any] | None = None  # structured-output contract
    tools: tuple[str, ...] = ()  # allowed Tool ports
    rubric: tuple[str, ...] = ()  # eval criteria the Critic scores against
    quality_bar: float = 0.75
    eval_score: float | None = None  # last recorded eval-vs-rubric score
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role, "version": self.version, "policy": self.policy,
            "exemplars": list(self.exemplars), "corpus": list(self.corpus),
            "outputSchema": self.output_schema, "tools": list(self.tools),
            "rubric": list(self.rubric), "qualityBar": self.quality_bar,
            "evalScore": self.eval_score, "metadata": dict(self.metadata),
        }


def from_dict(data: Mapping[str, Any]) -> SkillPack:
    return SkillPack(
        role=data["role"],
        version=str(data.get("version", "0")),
        policy=data.get("policy", ""),
        exemplars=tuple(data.get("exemplars") or ()),
        corpus=tuple(data.get("corpus") or ()),
        output_schema=data.get("output_schema") or data.get("outputSchema"),
        tools=tuple(data.get("tools") or ()),
        rubric=tuple(data.get("rubric") or ()),
        quality_bar=float(data.get("quality_bar", data.get("qualityBar", 0.75))),
        eval_score=data.get("eval_score", data.get("evalScore")),
        metadata=dict(data.get("metadata") or {}),
    )


class SkillPackRegistry:
    """Loads + serves skill packs by role; supports hot-loading a new version."""

    def __init__(self, packs: Mapping[str, SkillPack] | None = None) -> None:
        self._packs: dict[str, SkillPack] = dict(packs or {})

    def register(self, pack: SkillPack) -> None:
        self._packs[pack.role] = pack

    def get(self, role: str) -> SkillPack | None:
        return self._packs.get(role)

    def require(self, role: str) -> SkillPack:
        pack = self._packs.get(role)
        if pack is None:
            raise KeyError(f"no skill pack registered for role {role!r}")
        return pack

    def roles(self) -> list[str]:
        return sorted(self._packs)

    def __len__(self) -> int:
        return len(self._packs)


def load_pack(path: str | Path) -> SkillPack:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # lazy

        data = yaml.safe_load(text)
    else:
        import json

        data = json.loads(text)
    return from_dict(data)


def load_registry(directory: str | Path) -> SkillPackRegistry:
    """Load every ``*.yaml``/``*.yml``/``*.json`` skill pack from a directory."""
    directory = Path(directory)
    registry = SkillPackRegistry()
    if not directory.exists():
        return registry
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() in (".yaml", ".yml", ".json"):
            registry.register(load_pack(path))
    return registry
