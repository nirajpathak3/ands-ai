#!/usr/bin/env python3
"""End-to-end demo walkthrough (Day 14) — one command, fully offline.

Tells the whole story on one screen, deterministically, with **no server, no API
keys, and no network**: it drives the agent runtime in-process via FastAPI's
TestClient over the bundled Semgrep + SARIF sample reports.

    python scripts/demo_walkthrough.py            # narrated run
    python scripts/demo_walkthrough.py --quiet     # only the section headers
    python scripts/demo_walkthrough.py > docs/demo/walkthrough.md   # recorded run

The flow it narrates (the canonical reviewer story):
  1. health        — what's wired (provider, persistence, orchestration, egress, obs)
  2. reset + seed  — ingest the sample scanner reports through the full pipeline
  3. findings      — current-state view: SQLi auto-tickets, a medium waits, FP suppressed
  4. HITL          — a human approves the pending finding -> ticket is created
  5. idempotency   — re-seed: events grow, findings/tickets do not
  6. KPIs          — automation / approval / escalation split + latency
  7. AI Gateway    — cache-hit rate + cost (deterministic provider -> $0, offline)
  8. observability — firing alerts (zero offline) over governance/cost/reliability
  9. audit trail   — the append-only "why" behind the last few decisions
 10. policy        — a suppression rule deterministically overrides governance (audited)
 11. analytics     — trend roll-up + a Markdown executive report from the audit trail

It exits non-zero if any step fails, so it doubles as a smoke test.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Make the agent-runtime package importable without installing it, and pin the
# offline-by-default config (in-memory state, deterministic LLM, no OTel) so the
# walkthrough is reproducible regardless of the caller's environment.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "services" / "agent-runtime"))
for _key in ("DATABASE_URL", "REDIS_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(_key, None)
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")

# Keep the narrated transcript clean: the in-process tracer logs a line per span at
# INFO; the demo summarizes spans itself, so silence the tracer's own logging here.
logging.getLogger("secops.trace").setLevel(logging.WARNING)
logging.getLogger("secops.notify").setLevel(logging.WARNING)

# Render UTF-8 (em dashes, etc.) cleanly on Windows consoles and when redirected to
# a Markdown file, instead of the default cp1252 mojibake.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - older/odd streams
        pass

QUIET = False


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def say(*lines: str) -> None:
    if not QUIET:
        for line in lines:
            print(line)


def main() -> int:
    global QUIET
    parser = argparse.ArgumentParser(description="AI SecOps Copilot demo walkthrough")
    parser.add_argument("--quiet", action="store_true", help="print only headers")
    QUIET = parser.parse_args().quiet

    try:
        from fastapi.testclient import TestClient

        from app.main import app
    except Exception as exc:  # pragma: no cover - dependency hint
        print(
            "Could not import the agent runtime. Install it first:\n"
            "  cd services/agent-runtime && python -m pip install -e \".[dev]\"\n"
            f"(import error: {exc})",
            file=sys.stderr,
        )
        return 2

    client = TestClient(app)

    def get(path: str) -> dict:
        res = client.get(path)
        res.raise_for_status()
        return res.json()

    def post(path: str) -> dict:
        res = client.post(path)
        res.raise_for_status()
        return res.json()

    def post_json(path: str, body: dict, headers: dict | None = None) -> dict:
        res = client.post(path, json=body, headers=headers or {})
        res.raise_for_status()
        return res.json()

    # 1) Health -------------------------------------------------------------
    section("1. HEALTH — what's wired (all offline, no keys)")
    h = get("/health")
    say(
        f"  service        : {h['service']} v{h['version']} ({h['environment']})",
        f"  ticketProvider : {h['ticketProvider']}",
        f"  persistence    : {h['persistence']}",
        f"  orchestration  : {h['orchestration']}",
        f"  llm egress     : {h['llm']['egress']} "
        f"(providers={h['llm']['providers']}, cache={h['llm']['cacheEnabled']})",
        f"  observability  : tracing={h['observability']['tracing']}, "
        f"alertsFiring={h['observability']['alertsFiring']}",
        f"  governance     : auto>={h['governance']['autoThreshold']} "
        f"suppress>={h['governance']['suppressAutoThreshold']}",
    )

    # 2) Reset + seed -------------------------------------------------------
    section("2. RESET + SEED — ingest the bundled Semgrep + SARIF reports")
    post("/demo/reset")
    seed = post("/demo/seed")
    say(f"  seeded reports : {', '.join(seed['seeded'])}")
    for name, report in seed["reports"].items():
        summary = report.get("summary", {})
        say(f"    {name:<22} {summary}")

    # 3) Current-state findings --------------------------------------------
    section("3. FINDINGS — current-state view (deduped by finding_hash)")
    findings = get("/findings")["findings"]
    say(f"  {len(findings)} findings (one row per finding; the audit log keeps every event)")
    say("")
    say(f"  {'finding':<20}{'severity':<10}{'disposition':<16}{'outcome':<18}{'ticket':<14}")
    say(f"  {'-' * 76}")
    for f in findings:
        ticket = f.get("ticket")
        tk = f"{ticket['provider']}:{ticket['key']}" if ticket else (
            "(pending)" if f.get("pendingApproval") else "-"
        )
        say(
            f"  {f['findingId']:<20}{f['severity']:<10}{f['disposition']:<16}"
            f"{f['outcome']:<18}{tk:<14}"
        )

    # 4) Human-in-the-loop --------------------------------------------------
    section("4. HUMAN-IN-THE-LOOP — approve the pending finding -> ticket created")
    pending = [f for f in findings if f.get("pendingApproval")]
    if pending:
        target = pending[0]
        say(
            f"  pending: {target['findingId']} "
            f"(confidence={target['confidence']}, {target['disposition']})"
        )
        out = post(f"/approvals/{target['findingHash']}/approve")
        tk = out["ticket"]
        say(
            f"  approved by human -> {out['outcome']}: "
            f"{tk['provider']}:{tk['key']} ({tk['status']})"
        )
    else:
        say("  (no findings landed in the approval band this run)")

    # 5) Idempotency --------------------------------------------------------
    section("5. IDEMPOTENCY — re-seed the same reports (events grow, findings don't)")
    before = get("/metrics")
    post("/demo/seed")
    after = get("/metrics")
    say(
        f"  findingsProcessed : {before['findingsProcessed']} -> "
        f"{after['findingsProcessed']}  (unchanged: deduped)",
        f"  decisionEvents    : {before['decisionEvents']} -> "
        f"{after['decisionEvents']}  (grows: append-only audit log)",
        f"  ticketsCreated    : {before['ticketsCreated']} -> "
        f"{after['ticketsCreated']}  (unchanged: idempotent by finding_hash)",
    )

    # 6) KPIs ---------------------------------------------------------------
    section("6. KPIs — autonomy split + latency")
    m = get("/metrics")
    r = m["rates"]
    say(
        f"  findings processed : {m['findingsProcessed']}",
        f"  tickets created    : {m['ticketsCreated']}",
        f"  pending approvals  : {m['pendingApprovals']}",
        f"  escalations        : {m['escalations']}",
        f"  automation rate    : {r['automation'] * 100:.0f}%",
        f"  approval rate      : {r['approval'] * 100:.0f}%",
        f"  escalation rate    : {r['escalation'] * 100:.0f}%",
        f"  latency (mean/p95) : {m['latencyMs']['mean']} / {m['latencyMs']['p95']} ms",
    )

    # 7) AI Gateway ---------------------------------------------------------
    section("7. AI GATEWAY — single LLM egress (cache + cost)")
    g = get("/gateway/metrics")
    say(
        f"  configured       : {g.get('providers')}  (deterministic always-on fallback)",
        f"  requests         : {g.get('totalRequests', 0)}",
        f"  cache hits       : {g.get('cacheHits', 0)}  "
        f"({g.get('cacheHitRate', 0.0) * 100:.0f}% hit rate)",
        f"  fallbacks used   : {g.get('fallbackUsed', 0)}  "
        f"({g.get('fallbackRate', 0.0) * 100:.0f}% rate)",
        f"  total cost (USD) : {g.get('totalCostUsd', 0.0)}  (offline -> free)",
    )

    # 8) Observability ------------------------------------------------------
    section("8. OBSERVABILITY — alert rule engine over governance/cost/reliability")
    alerts = get("/observability/alerts")
    if alerts["count"] == 0:
        say("  0 alerts firing — healthy (no escalation spike, no dead-letters, costs nominal)")
    else:
        for a in alerts["alerts"]:
            say(f"  [{a.get('severity', '?').upper()}] {a.get('name')}: {a.get('message')}")
    prom = client.get("/observability/metrics")
    say(
        f"  Prometheus scrape : {prom.status_code} "
        f"({len(prom.text.splitlines())} lines of text exposition at /observability/metrics)"
    )

    # 9) Audit trail --------------------------------------------------------
    section("9. AUDIT TRAIL — append-only 'why' (last 6 events)")
    audit = get("/audit")
    say(f"  {audit['count']} total events (compliance log)")
    say("")
    say(f"  {'finding':<20}{'disposition':<16}{'reasonCode':<32}{'actor'}")
    say(f"  {'-' * 76}")
    for rec in audit["records"][-6:]:
        say(
            f"  {rec['findingId']:<20}{rec['disposition']:<16}"
            f"{rec['reasonCode']:<32}{rec['actor']}"
        )

    # 10) Policy-as-code ----------------------------------------------------
    section("10. POLICY-AS-CODE — deterministic override on top of governance")
    pol = {"X-Tenant-Id": "policy-demo"}
    post_json("/demo/reset", {}, pol)
    sqli = {
        "id": "F-DEMO-SQLI", "ruleId": "formatted-sql-query", "title": "SQL injection",
        "message": "user input flows into a SQL query", "file": "app/api/users.py",
        "startLine": 42, "cwe": "CWE-89", "scannerSeverity": "ERROR",
        "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
    }
    before = post_json("/analyze", {"finding": sqli}, pol)["decision"]
    say(
        f"  without policy : {before['disposition']} / "
        f"{before['analysis']['recommendedAction']}  ({before['reasonCode']})"
    )
    rule = {"id": "fp-sql-pattern", "action": "suppress",
            "ruleIds": ["formatted-sql-query"], "reason": "known false-positive pattern"}
    post_json("/policy/rules", {"rules": [rule]}, pol)
    after = post_json("/analyze", {"finding": sqli}, pol)
    dec = after["decision"]
    say(
        "  rule applied   : suppress where ruleId=formatted-sql-query",
        f"  with policy    : {dec['disposition']} / "
        f"{dec['analysis']['recommendedAction']}  ({dec['reasonCode']}) "
        f"-> action={after['action']['outcome']}",
    )
    hits = client.get("/policy", headers=pol).json()["hits"]
    say(f"  policy hits    : {hits}  (audited as reasonCode=policy:<id>)")

    # 11) Trend analytics ---------------------------------------------------
    section("11. ANALYTICS — trend roll-up + Markdown executive report")
    summ = get("/analytics/summary")
    rates = summ["rates"]
    rem = summ.get("remediation", {})
    say(
        f"  decisions          : {summ['decisions']}",
        f"  automation rate    : {rates['automation'] * 100:.0f}%  "
        f"(suppression {rates['suppression'] * 100:.0f}%)",
        f"  suppressions       : {summ['suppressions']} "
        f"({summ['policySuppressions']} by policy)",
        f"  resolved / MTTR    : {summ['resolved']} / {rem.get('mttrHoursMean', 0)}h",
        f"  SLA compliance     : {rem.get('slaCompliance', 1.0) * 100:.0f}%",
    )
    report = client.get("/analytics/report").text.splitlines()
    say("", "  --- GET /analytics/report (Markdown, first lines) ---")
    for line in report[:10]:
        say(f"  {line}")

    section("DEMO COMPLETE")
    say(
        "  Ran the full lifecycle offline: ingest -> RAG-grounded analysis -> governed",
        "  decision -> action (auto / human-approval / escalate) -> metrics, gateway,",
        "  alerts, and an auditable trail — deterministically, with zero external calls.",
        "",
        "  Live version: `python -m uvicorn app.main:app --port 8088` then open",
        "  http://localhost:8088/ for the operations dashboard.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
