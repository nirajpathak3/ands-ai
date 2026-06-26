#!/usr/bin/env python3
"""Live-path demo with a FAKE provider — proves FORGE_MODE=live end-to-end, NO API keys.

Same lifecycle as the offline demo, but the AI Gateway routes to a scripted ``fake-live``
provider that behaves like a real model: it *generates* structured JSON for the agents'
output contract (so you see model-written content, not the offline seed), occasionally
returns invalid output to trigger the **bounded reprompt**, answers the Critic/Red-team as
an **LLM-as-judge**, and reports **simulated, non-zero cost**. Fully deterministic.

    python scripts/demo_live_fake.py
    python scripts/demo_live_fake.py --vision "your product idea" --no-flaky

Exits non-zero if any step fails, so it doubles as a smoke test of the live path.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
for _key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):  # prove it needs no real keys
    os.environ.pop(_key, None)

for _stream in (sys.stdout, sys.stderr):  # clean UTF-8 on Windows consoles
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from forge_kernel.config import Settings  # noqa: E402
from forge_kernel.runner import RunStore  # noqa: E402
from forge_kernel.state import RunStatus  # noqa: E402
from forge_os import build_forge  # noqa: E402

DEFAULT_VISION = (
    "A platform that helps small teams run governed AI agents safely, with approvals, "
    "evals, and a full audit trail."
)


def h(title: str) -> None:
    print(f"\n{'=' * 72}\n  {title}\n{'=' * 72}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision", default=DEFAULT_VISION)
    parser.add_argument("--no-flaky", action="store_true",
                        help="disable the injected invalid-then-reprompt behavior")
    parser.add_argument("--keep", action="store_true", help="keep the temp workspace")
    args = parser.parse_args()

    workspace = tempfile.mkdtemp(prefix="forge-live-fake-")
    # LIVE mode + the scripted provider (no keys needed). Built explicitly so the demo is
    # independent of process env / import order.
    settings = Settings(mode="live", fake_live=True, fake_live_flaky=not args.no_flaky,
                        workspace=workspace)
    forge = build_forge(settings=settings, store=RunStore(workspace))

    h("0. MODE — live path, scripted provider, no API keys")
    print(f"  mode={settings.mode}  fake_live={settings.fake_live}  "
          f"flaky={settings.fake_live_flaky}  offline={settings.offline}")
    print(f"  OPENAI_API_KEY set={bool(os.environ.get('OPENAI_API_KEY'))}  "
          f"ANTHROPIC_API_KEY set={bool(os.environ.get('ANTHROPIC_API_KEY'))}")

    h("1. VISION IN — start the run")
    print(f"  vision: {args.vision}")
    run = forge.start(args.vision)
    print(f"  -> status={run.status}  stage={run.current_stage}")

    h("2. AUTONOMY + HITL — approve each gate (Critic/Red-team scored by LLM-as-judge)")
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 20:
        guard += 1
        g = run.pending_gate
        print(f"  GATE [{g['stage']}] mode={g['mode']} eval={g['evalScore']} -> APPROVE")
        run = forge.resume(run.run_id, approved=True, feedback="approved in demo")
    print(f"  -> final status={run.status}  cost=${run.cost_usd:.4f}  tokens={run.tokens}")

    h("3. ARTIFACTS — model-generated (cost/tokens per artifact; fallback flagged)")
    for key, art in run.artifacts.items():
        fb = " [seed-fallback]" if isinstance(art.content, dict) and "_fallback" in art.content \
            else ""
        extra = f"  -> {art.path}" if art.path else ""
        print(f"  {key:22s} {art.status:11s} eval={art.eval_score} "
              f"cost=${art.cost_usd:.5f} tok={art.tokens}{fb}{extra}")

    h("4. CONTENT — proof it is model-written, not the offline seed (one sample)")
    sample = run.artifacts.get("vision_brief") or next(iter(run.artifacts.values()))
    if isinstance(sample.content, dict):
        for k, v in list(sample.content.items())[:3]:
            print(f"  {k}: {str(v)[:90]}")

    h("5. AI GATEWAY — egress provider + SIMULATED cost (live path)")
    m = forge.gateway.metrics()
    fake_reqs = m["byProvider"].get("fake-live", 0)
    n_art = len(run.artifacts)
    print(f"  requests={m['totalRequests']} byProvider={m['byProvider']}")
    print(f"  providers={m['providers']} cacheHitRate={m['cacheHitRate']} "
          f"fallbackRate={m['fallbackRate']} costPerRequest=${m['costPerRequestUsd']}")
    if settings.fake_live_flaky:
        print(f"  reprompts: fake-live served {fake_reqs} calls for ~{n_art} artifacts "
              f"(extra calls = bounded reprompts after an injected invalid response)")

    art_dir = Path(run.workspace_dir)
    mockup = art_dir / "ux" / "mockup.html"
    repos = list((art_dir / "scaffold").glob("*/README.md"))
    used_fake = m["byProvider"].get("fake-live", 0) > 0
    ok = (run.status == RunStatus.COMPLETED and mockup.exists() and bool(repos)
          and used_fake and run.cost_usd > 0)
    h("RESULT")
    print(f"  {'PASS' if ok else 'FAIL'} — live path ran via '{', '.join(m['providers'])}', "
          f"produced eval-passing artifacts + scaffold, at simulated cost ${run.cost_usd:.4f}.")
    if args.keep:
        print(f"  workspace kept at: {workspace}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
