"""Cross-cutting reviewers: Critic + Red-team (PRODUCT_VISION §4, mandatory every stage).

Before any artifact reaches a gate it is scored by the **Critic** (quality vs the
artifact's rubric) and probed by the **Red-team** (adversarial gaps/risks). Offline this
is deterministic: the Critic scores rubric coverage over the produced content, and the
Red-team flags any rubric criterion that is unsatisfied plus a couple of generic
adversarial checks. The same seam upgrades to LLM-as-judge through the AI Gateway (task=
"judge") in a later build step without changing the gate logic that consumes the score.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..blueprint import ArtifactSpec
from ..state import ArtifactRecord

_TOKEN = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _content_text(content: dict) -> str:
    parts: list[str] = []

    def walk(value) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for k, v in value.items():
                parts.append(str(k))
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        elif value is not None:
            parts.append(str(value))

    walk(content)
    return " ".join(parts)


def _criterion_satisfied(criterion: str, content: dict, text_tokens: set[str]) -> bool:
    """A criterion is met if a populated content field maps to it, or the text covers it."""
    crit_tokens = _norm(criterion)
    if not crit_tokens:
        return True
    # Direct field hit: a non-empty content key whose tokens overlap the criterion.
    for key, value in content.items():
        if value in (None, "", [], {}):
            continue
        if crit_tokens & _norm(str(key)):
            return True
    # Coverage in the artifact text (the criterion's salient tokens are present).
    return crit_tokens.issubset(text_tokens)


@dataclass
class ReviewResult:
    critic_score: float
    redteam_findings: list[str] = field(default_factory=list)

    @property
    def eval_score(self) -> float:
        # Red-team findings apply a small, bounded penalty on top of the Critic score so
        # adversarial gaps actually move the gate signal (never below 0).
        penalty = min(0.15, 0.05 * len(self.redteam_findings))
        return round(max(0.0, self.critic_score - penalty), 4)


# A judge refines the deterministic heuristic with LLM-as-judge scoring. It receives the
# heuristic result and returns a (possibly) adjusted one; offline it is a no-op. Injected by
# the program so the kernel stays provider-agnostic.
Judge = Callable[[ArtifactSpec, ArtifactRecord, "ReviewResult"], "ReviewResult"]


class Reviewer:
    """Critic + Red-team. Deterministic heuristic by default (the offline eval signal);
    an optional ``judge`` upgrades it to LLM-as-judge in live mode behind the same seam."""

    def __init__(self, judge: Judge | None = None) -> None:
        self._judge = judge

    def review(self, spec: ArtifactSpec, record: ArtifactRecord) -> ReviewResult:
        result = self._heuristic(spec, record)
        if self._judge is not None:
            try:
                result = self._judge(spec, record, result)
            except Exception:  # noqa: BLE001 - a judge failure must never block the gate
                pass
        return result

    def _heuristic(self, spec: ArtifactSpec, record: ArtifactRecord) -> ReviewResult:
        content = record.content or {}
        text_tokens = _norm(_content_text(content))

        rubric = spec.rubric
        if rubric:
            satisfied = [
                c for c in rubric if _criterion_satisfied(c, content, text_tokens)
            ]
            critic_score = len(satisfied) / len(rubric)
            findings = [f"gap: rubric criterion not evidenced — {c}" for c in rubric
                        if c not in satisfied]
        else:
            # No rubric: score on substance (how many fields carry real content).
            populated = sum(1 for v in content.values() if v not in (None, "", [], {}))
            critic_score = min(1.0, 0.5 + 0.15 * populated) if content else 0.0
            findings = [] if populated >= 2 else ["gap: artifact has little substance"]

        # Generic adversarial probes (cheap, deterministic, domain-agnostic).
        if not content:
            findings.append("redteam: empty artifact")
        if isinstance(content.get("risks"), (list, str)) and not content.get("risks"):
            findings.append("redteam: declared 'risks' field is empty")

        return ReviewResult(critic_score=round(critic_score, 4), redteam_findings=findings)
