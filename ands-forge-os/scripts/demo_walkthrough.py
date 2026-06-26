#!/usr/bin/env python3
"""End-to-end demo walkthrough — one command, fully offline, deterministic.

Tells the whole ANDS Forge OS story on one screen with NO server, NO API keys, and NO
network: a product vision goes in; Forge compiles a plan, runs Discovery agents in
parallel, pauses at each HITL gate (which we auto-approve here), renders an HTML mockup,
scaffolds a real product repo on disk, and finishes with a full cost + audit trail.

    python scripts/demo_walkthrough.py
    python scripts/demo_walkthrough.py --vision "your product idea"

Exits non-zero if any step fails, so it doubles as a smoke test.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Make the kernel + program importable without installing, and pin offline defaults.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
for _key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(_key, None)
os.environ.setdefault("FORGE_MODE", "offline")

for _stream in (sys.stdout, sys.stderr):  # clean UTF-8 on Windows consoles
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass

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

    workspace = tempfile.mkdtemp(prefix="forge-demo-")
    forge = build_forge(store=RunStore(workspace))

    h("1. BLUEPRINT — the product-development program (loaded as data)")
    for stage in forge.blueprint.ordered_stages():
        mode = stage.gate_mode or forge.settings.default_gate_mode
        kind = "stub/auto-pass" if stage.auto_pass else f"gate={mode}"
        arts = ", ".join(a.key for a in stage.artifacts)
        print(f"  [{stage.order}] {stage.title:24s} {kind:18s} :: {arts}")

    h("2. VISION IN — start the run (autonomous until the first gate)")
    print(f"  vision: {args.vision}")
    run = forge.start(args.vision)
    print(f"  -> status={run.status}  stage={run.current_stage}")

    h("3. AUTONOMY + HITL — approve each gate; agents run in parallel between gates")
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 20:
        guard += 1
        g = run.pending_gate
        print(f"  GATE [{g['stage']}] mode={g['mode']} eval={g['evalScore']} -> APPROVE")
        run = forge.resume(run.run_id, approved=True, feedback="approved in demo")
    print(f"  -> final status={run.status}  cost=${run.cost_usd:.4f}")

    h("4. PARALLELISM — Discovery fanned out (from the audit trail)")
    for e in forge.audit_for(run.run_id):
        if e["reason_code"] == "stage_completed" and e["data"].get("maxParallelism", 1) > 1:
            print(f"  {e['stage']:12s} waves={e['data']['waves']} "
                  f"maxParallelism={e['data']['maxParallelism']}")

    h("5. ARTIFACTS — what Forge produced")
    for key, art in run.artifacts.items():
        extra = f"  -> {art.path}" if art.path else ""
        print(f"  {key:22s} {art.status:11s} eval={art.eval_score}{extra}")

    h("6. TANGIBLE OUTPUT — on disk")
    art_dir = Path(run.workspace_dir)
    mockup = art_dir / "ux" / "mockup.html"
    print(f"  mockup : {mockup}  exists={mockup.exists()}")
    repos = list((art_dir / "scaffold").glob("*/README.md"))
    for r in repos:
        files = sum(1 for _ in r.parent.rglob("*") if _.is_file())
        print(f"  repo   : {r.parent}  ({files} files)")

    h("7. AI GATEWAY — egress cost + cache (offline = $0)")
    m = forge.gateway.metrics()
    print(f"  requests={m['totalRequests']} byProvider={m['byProvider']} "
          f"cacheHitRate={m['cacheHitRate']} costPerRequest=${m['costPerRequestUsd']}")

    h("8. AUDIT — the append-only 'why' (last 8 events)")
    for e in forge.audit_for(run.run_id)[-8:]:
        loc = f"{e['stage'] or '-'}/{e['artifact'] or '-'}"
        print(f"  {e['reason_code']:24s} {e['actor']:10s} {loc:28s} {e['detail'][:40]}")

    ok = run.status == RunStatus.COMPLETED and mockup.exists() and bool(repos)
    h("RESULT")
    print(f"  {'PASS' if ok else 'FAIL'} — vision in -> approved, eval-passing artifact "
          f"set + scaffolded repo out, fully audited.")
    if args.keep:
        print(f"  workspace kept at: {workspace}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
