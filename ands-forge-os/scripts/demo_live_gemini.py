#!/usr/bin/env python3
"""End-to-end demo against the REAL Gemini provider (uses your .env key).

Same story as scripts/demo_walkthrough.py, but live: agents call Gemini through the AI
Gateway, validate structured output, and reprompt on invalid JSON. If the model ever fails
(rate limit, network, bad JSON) the gateway falls back to the deterministic seed, so the
run never hard-fails. Cost reflects real Gemini usage (free tier ~ $0).

    python scripts/demo_live_gemini.py
    python scripts/demo_live_gemini.py --vision "your product idea"

Requires FORGE_MODE=live and GEMINI_API_KEY in .env (this script does NOT mock anything).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

for _stream in (sys.stdout, sys.stderr):  # clean UTF-8 on Windows consoles
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from forge_kernel.config import get_settings  # noqa: E402
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
    parser.add_argument("--keep", action="store_true", help="keep the temp workspace")
    args = parser.parse_args()

    settings = get_settings()
    h("0. PRECHECK — live mode + a configured provider")
    print(f"  FORGE_MODE      = {settings.mode}")
    print(f"  gemini key set  = {bool(settings.gemini_api_key)}  model={settings.gemini_model}")
    print(f"  model tiers     = strong:{settings.model_strong}  cheap:{settings.model_cheap}")
    if settings.offline or not settings.gemini_api_key:
        print("\n  ABORT: need FORGE_MODE=live and GEMINI_API_KEY in .env. See .env.example.")
        return 2

    workspace = tempfile.mkdtemp(prefix="forge-live-")
    forge = build_forge(store=RunStore(workspace))

    h("1. VISION IN — start the run (autonomous until the first gate)")
    print(f"  vision: {args.vision}")
    run = forge.start(args.vision)
    print(f"  -> status={run.status}  stage={run.current_stage}")

    h("2. AUTONOMY + HITL — approve each gate; agents call Gemini between gates")
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 20:
        guard += 1
        g = run.pending_gate
        print(f"  GATE [{g['stage']}] mode={g['mode']} eval={g['evalScore']} -> APPROVE")
        run = forge.resume(run.run_id, approved=True, feedback="approved in live demo")
    print(f"  -> final status={run.status}  cost=${run.cost_usd:.4f}")

    h("3. ARTIFACTS — what Forge produced (ACTUAL provider/model per artifact)")
    for key, art in run.artifacts.items():
        served = (f"{art.served_provider}:{art.served_model}"
                  if art.served_provider else "—")
        extra = f"  -> {art.path}" if art.path else ""
        print(f"  {key:22s} {art.status:11s} served={served:28s} eval={art.eval_score}{extra}")

    h("4. TANGIBLE OUTPUT — on disk")
    art_dir = Path(run.workspace_dir)
    mockup = art_dir / "ux" / "mockup.html"
    print(f"  mockup : {mockup}  exists={mockup.exists()}")
    repos = list((art_dir / "scaffold").glob("*/README.md"))
    for r in repos:
        files = sum(1 for _ in r.parent.rglob("*") if _.is_file())
        print(f"  repo   : {r.parent}  ({files} files)")

    h("5. AI GATEWAY — real egress: provider mix + cost + cache")
    m = forge.gateway.metrics()
    print(f"  requests={m['totalRequests']} byProvider={m['byProvider']} "
          f"cacheHitRate={m['cacheHitRate']} costPerRequest=${m['costPerRequestUsd']}")

    h("6. AUDIT — the append-only 'why' (last 8 events)")
    for e in forge.audit_for(run.run_id)[-8:]:
        loc = f"{e['stage'] or '-'}/{e['artifact'] or '-'}"
        print(f"  {e['reason_code']:24s} {e['actor']:10s} {loc:28s} {e['detail'][:40]}")

    ok = run.status == RunStatus.COMPLETED and mockup.exists() and bool(repos)
    h("RESULT")
    print(f"  {'PASS' if ok else 'FAIL'} — live vision in -> approved, eval-passing artifact "
          f"set + scaffolded repo out, fully audited.")
    if args.keep:
        print(f"  workspace kept at: {workspace}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
