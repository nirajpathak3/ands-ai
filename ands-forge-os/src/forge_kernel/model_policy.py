"""Per-task / per-stage model selection (the "which model does which stage" dial).

Resolution order, most specific first:

  1. an explicit ``override`` (a blueprint artifact/stage ``model:`` value) — you pinned it;
  2. otherwise a **tier** chosen from the task + stage:
       * the ``judge`` task (Critic/Red-team) and any stage in ``settings.strong_stages``
         use the **strong** tier (reasoning-heavy);
       * everything else uses the **cheap** tier (high-volume drafting);
  3. the tier maps to ``settings.model_strong`` / ``settings.model_cheap``.

Returns ``None`` when no model is configured (offline/deterministic ignore the model, and
real providers then fall back to their own default), so this is safe in every mode. Swapping
models as new ones ship is a one-line env/blueprint edit — no code change.
"""

from __future__ import annotations

from .config import Settings


def resolve_model(
    settings: Settings, *, task: str, stage: str | None = None, override: str | None = None
) -> str | None:
    if override:
        return override
    strong = task == "judge" or (stage is not None and stage in settings.strong_stages)
    model = settings.model_strong if strong else settings.model_cheap
    return model or None
