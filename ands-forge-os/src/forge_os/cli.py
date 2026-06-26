"""CLI for ANDS Forge OS — script + CI gate driver for the run lifecycle.

    forge start "A platform that helps small teams run governed AI agents"
    forge status <run_id>
    forge approve <run_id> [--feedback "..."]
    forge reject  <run_id> --feedback "tighten the metrics"
    forge audit   <run_id>
    forge run "vision..."          # start + auto-approve every gate (great for demos/CI)

Offline-deterministic by default (no keys, $0). Shares the durable RunStore with the API,
so a run started on the CLI can be approved from the dashboard and vice versa.
"""

from __future__ import annotations

import argparse
import json
import sys

from forge_kernel.state import RunStatus
from forge_os import build_forge


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _summary(forge, run) -> dict:
    return {
        "runId": run.run_id,
        "status": str(run.status),
        "currentStage": run.current_stage,
        "costUsd": run.cost_usd,
        "pendingGate": run.pending_gate,
        "workspace": run.workspace_dir,
    }


def cmd_start(forge, args) -> int:
    run = forge.start(args.vision)
    _print(_summary(forge, run))
    return 0


def cmd_run(forge, args) -> int:
    """Start and auto-approve every HITL gate until the run finishes."""
    run = forge.start(args.vision)
    guard = 0
    while run.status == RunStatus.AWAITING_APPROVAL and guard < 50:
        guard += 1
        print(f"[gate] auto-approving {run.pending_gate['stage']} "
              f"(eval {run.pending_gate['evalScore']}, mode {run.pending_gate['mode']})",
              file=sys.stderr)
        run = forge.resume(run.run_id, approved=True, feedback="auto-approved (forge run)")
    _print(_summary(forge, run))
    if run.status != RunStatus.COMPLETED:
        return 1
    return 0


def cmd_status(forge, args) -> int:
    _print(forge.status_summary(args.run_id))
    return 0


def cmd_approve(forge, args) -> int:
    run = forge.resume(args.run_id, approved=True, feedback=args.feedback)
    _print(_summary(forge, run))
    return 0


def cmd_reject(forge, args) -> int:
    run = forge.resume(args.run_id, approved=False, feedback=args.feedback)
    _print(_summary(forge, run))
    return 0


def cmd_audit(forge, args) -> int:
    _print(forge.audit_for(args.run_id))
    return 0


def cmd_list(forge, args) -> int:
    _print({"runs": forge.store.list_runs()})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge", description="ANDS Forge OS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="start a run (pauses at the first HITL gate)")
    p.add_argument("vision")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("run", help="start + auto-approve all gates (demo/CI)")
    p.add_argument("vision")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="show a run's status")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("approve", help="approve the pending gate and resume")
    p.add_argument("run_id")
    p.add_argument("--feedback", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="reject the pending gate (reopens the stage)")
    p.add_argument("run_id")
    p.add_argument("--feedback", default="")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("audit", help="print a run's audit trail")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("list", help="list runs")
    p.set_defaults(func=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    forge = build_forge()
    try:
        return args.func(forge, args)
    except (KeyError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
