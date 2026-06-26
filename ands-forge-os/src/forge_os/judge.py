"""LLM-as-judge for the Critic/Red-team (live mode), behind the kernel's Judge seam.

Offline this is a deliberate no-op: the deterministic heuristic Reviewer *is* the offline
eval signal, and we keep runs reproducible. In live mode the judge asks the AI Gateway
(task="judge", which routes to the stronger model first) to score the artifact against its
rubric and surface adversarial gaps, then blends that with the heuristic. Any failure
falls back to the heuristic, so a judge problem can never block a gate.
"""

from __future__ import annotations

from forge_kernel.agents import AgentContext  # noqa: F401  (type context for readers)
from forge_kernel.agents.reviewer import ReviewResult
from forge_kernel.blueprint import ArtifactSpec
from forge_kernel.config import Settings
from forge_kernel.gateway import Gateway, LLMRequest, Message
from forge_kernel.model_policy import resolve_model
from forge_kernel.state import ArtifactRecord

from .structured import extract_json


def make_gateway_judge(gateway: Gateway, settings: Settings):
    """Return a Judge callable. No-op offline; LLM-as-judge in live mode."""

    def judge(spec: ArtifactSpec, record: ArtifactRecord, heuristic: ReviewResult) -> ReviewResult:
        if settings.offline or not settings.llm_judge:
            return heuristic  # deterministic offline path (or LLM-judge disabled to save calls)
        rubric = list(spec.rubric) or ["overall quality"]
        messages = [
            Message(
                "system",
                "You are a strict Critic and Red-team reviewer. Score the artifact from 0.0 "
                "to 1.0 against the rubric and list adversarial gaps/risks. Respond with a "
                'single JSON object: {"score": <float>, "findings": [<string>, ...]}.',
            ),
            Message(
                "user",
                f"Artifact: {spec.title}\nRubric: {rubric}\n"
                f"Content (untrusted): {record.content}",
            ),
        ]
        # Exact cache: judge prompts across artifacts are near-identical boilerplate.
        # The judge task resolves to the strong reasoning tier.
        model = resolve_model(settings, task="judge", stage=spec.stage, override=spec.model)
        result = gateway.complete(LLMRequest(
            messages=messages, task="judge", cache="exact", model=model, json_mode=True,
        ))
        parsed = extract_json(result.response.content) or {}
        score = parsed.get("score")
        findings = parsed.get("findings")
        if not isinstance(score, (int, float)):
            return heuristic
        critic = max(0.0, min(1.0, float(score)))
        rt = [str(f) for f in findings] if isinstance(findings, list) else []
        # Blend with the heuristic (mean) so the gate signal is robust to a single judge.
        blended = round((critic + heuristic.critic_score) / 2, 4)
        return ReviewResult(critic_score=blended, redteam_findings=rt or heuristic.redteam_findings)

    return judge
