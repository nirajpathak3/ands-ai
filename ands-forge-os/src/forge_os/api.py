"""FastAPI edge for ANDS Forge OS — REST + a lightweight run dashboard.

The kernel is headless; this is one client. It exposes the run lifecycle (start, status,
approve/reject a gate, fetch artifacts/audit/traces), serves the rendered HTML mockup, and
renders a tiny dashboard so you can watch a run, see the pending gate, and click through to
the mockup and scaffolded repo. A single ``Forge`` instance (shared ``RunStore``) backs it.
"""

from __future__ import annotations

import html

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from forge_kernel.config import get_settings
from forge_kernel.model_policy import resolve_model
from forge_os import build_forge

settings = get_settings()
forge = build_forge(settings)

app = FastAPI(
    title="ANDS Forge OS",
    description="Autonomous, multi-agent product-development operating system.",
    version="0.1.0",
)


class StartRequest(BaseModel):
    vision: str


class GateDecision(BaseModel):
    feedback: str = ""


def _run_or_404(run_id: str):
    try:
        return forge.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id}") from exc


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ands-forge-os",
        "mode": settings.mode,
        "blueprint": f"{forge.blueprint.name} v{forge.blueprint.version}",
        "providers": forge.gateway.metrics()["providers"],
    }


@app.get("/blueprint")
def blueprint() -> dict:
    bp = forge.blueprint
    return {
        "name": bp.name,
        "version": bp.version,
        "description": bp.description,
        "stages": [
            {
                "key": s.key, "title": s.title, "order": s.order,
                "gateMode": s.gate_mode or settings.default_gate_mode,
                "autoPass": s.auto_pass,
                "artifacts": [{"key": a.key, "title": a.title, "role": a.role}
                              for a in s.artifacts],
            }
            for s in bp.ordered_stages()
        ],
    }


@app.post("/runs")
def start_run(req: StartRequest) -> dict:
    if not req.vision.strip():
        raise HTTPException(status_code=400, detail="vision must not be empty")
    run = forge.start(req.vision)
    return forge.status_summary(run.run_id)


@app.get("/runs")
def list_runs() -> dict:
    runs = []
    for run_id in forge.store.list_runs():
        run = forge.get(run_id)
        runs.append({
            "runId": run.run_id, "status": str(run.status), "vision": run.vision[:120],
            "currentStage": run.current_stage, "costUsd": run.cost_usd,
        })
    return {"runs": runs}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return _run_or_404(run_id).to_dict()


@app.get("/runs/{run_id}/audit")
def get_audit(run_id: str) -> dict:
    _run_or_404(run_id)
    return {"events": forge.audit_for(run_id)}


@app.get("/runs/{run_id}/artifacts/{key}")
def get_artifact(run_id: str, key: str) -> dict:
    run = _run_or_404(run_id)
    art = run.artifacts.get(key)
    if art is None:
        raise HTTPException(status_code=404, detail=f"unknown artifact {key}")
    return art.to_dict()


@app.post("/runs/{run_id}/approve")
def approve(run_id: str, body: GateDecision | None = None) -> dict:
    run = _run_or_404(run_id)
    if str(run.status) != "awaiting_approval":
        raise HTTPException(status_code=409, detail=f"run is {run.status}, not awaiting")
    result = forge.resume(run_id, approved=True, feedback=(body.feedback if body else ""))
    return forge.status_summary(result.run_id)


@app.post("/runs/{run_id}/reject")
def reject(run_id: str, body: GateDecision | None = None) -> dict:
    run = _run_or_404(run_id)
    if str(run.status) != "awaiting_approval":
        raise HTTPException(status_code=409, detail=f"run is {run.status}, not awaiting")
    result = forge.resume(run_id, approved=False, feedback=(body.feedback if body else ""))
    return forge.status_summary(result.run_id)


@app.get("/runs/{run_id}/mockup", response_class=HTMLResponse)
def get_mockup(run_id: str) -> HTMLResponse:
    _run_or_404(run_id)
    path = forge.store.artifacts_dir(run_id) / "ux" / "mockup.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no mockup rendered yet")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/gateway/metrics")
def gateway_metrics() -> dict:
    return forge.gateway.metrics()


def _models_summary(run_id: str | None = None) -> dict:
    """Resolve which model each stage/artifact uses (tier dial), with per-stage cost.

    The mapping comes from settings + the blueprint (no run needed). Pass ``run_id`` to
    overlay the actual per-stage cost/tokens recorded for that run.
    """
    run = _run_or_404(run_id) if run_id else None
    stages = []
    for s in forge.blueprint.ordered_stages():
        artifacts = []
        stage_cost = 0.0
        stage_tokens = 0
        for a in s.artifacts:
            rec = run.artifacts.get(a.key) if run else None
            if rec is not None:
                stage_cost += rec.cost_usd
                stage_tokens += rec.tokens
            if s.auto_pass or a.auto_pass:
                draft = judge = "— (auto-pass, no LLM)"
                tier = "auto-pass"
            else:
                draft = resolve_model(settings, task="draft", stage=s.key, override=a.model)
                judge = resolve_model(settings, task="judge", stage=s.key, override=a.model)
                tier = ("pinned" if a.model else
                        ("strong" if s.key in settings.strong_stages else "cheap"))
            artifacts.append({
                "key": a.key, "title": a.title, "role": a.role, "tier": tier,
                "draftModel": draft, "judgeModel": judge,
                "modelOverride": a.model,
                "costUsd": round(rec.cost_usd, 6) if rec else None,
                "tokens": rec.tokens if rec else None,
                # What actually served it (reflects gateway fallback, e.g. gemini -> groq).
                "servedProvider": rec.served_provider if rec else None,
                "servedModel": rec.served_model if rec else None,
            })
        stages.append({
            "key": s.key, "title": s.title, "order": s.order, "autoPass": s.auto_pass,
            "artifacts": artifacts,
            "stageCostUsd": round(stage_cost, 6) if run else None,
            "stageTokens": stage_tokens if run else None,
        })
    return {
        "mode": settings.mode,
        "effectiveProvider": ("deterministic (offline)" if settings.offline
                              else "routed (live)"),
        "tiers": {
            "strong": settings.model_strong, "cheap": settings.model_cheap,
            "strongStages": list(settings.strong_stages),
        },
        "providers": forge.gateway.metrics()["providers"],
        "runId": run.run_id if run else None,
        "totalCostUsd": run.cost_usd if run else None,
        "stages": stages,
    }


@app.get("/models")
def models(run_id: str | None = None) -> dict:
    return _models_summary(run_id)


@app.get("/models/view", response_class=HTMLResponse)
def models_view(run_id: str | None = None) -> HTMLResponse:
    return HTMLResponse(_models_html(_models_summary(run_id)))


@app.get("/observability/traces")
def traces(limit: int = 50) -> dict:
    return {"spans": forge.tracer.recent(limit)}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(_dashboard_html())


_MODELS_CSS = """
body{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#0f1221;color:#e7e9f5}
header{padding:20px 32px;border-bottom:1px solid #2a3158;background:#171a30}
h1{margin:0;font-size:20px} p{color:#9aa3c7;margin:4px 0 0}
main{padding:24px 32px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:18px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #2a3158}
th{color:#9aa3c7;font-weight:600}
h2{font-size:15px;margin:18px 0 6px}
.pill{padding:2px 8px;border-radius:999px;font-size:11px}
.strong{background:#3a2a6a;color:#c7b6ff}
.cheap{background:#1a3a5a;color:#7cc4ff}
.pinned{background:#5a4a16;color:#ffe08a}
.auto-pass{background:#2a3158;color:#9aa3c7}
.served{background:#143a2a;color:#7ee2a8}
.note{background:#171a30;border:1px solid #2a3158;border-radius:8px;padding:10px 14px;
      margin-bottom:16px;color:#9aa3c7}
code{color:#7ee2a8} a{color:#7cc4ff}
.tot{color:#7ee2a8;font-weight:600}
</style>"""


def _models_html(data: dict) -> str:
    tiers = data["tiers"]
    rows = []
    for s in data["stages"]:
        cost = (f" · <span class='tot'>${s['stageCostUsd']:.5f}</span> · "
                f"{s['stageTokens']} tok" if s["stageCostUsd"] is not None else "")
        rows.append(f"<h2>[{s['order']}] {html.escape(s['title'])}{cost}</h2>")
        body = []
        for a in s["artifacts"]:
            c = f"${a['costUsd']:.5f}" if a["costUsd"] is not None else "-"
            tok = a["tokens"] if a["tokens"] is not None else "-"
            if a.get("servedProvider"):
                served = (f"<span class='pill served'>{html.escape(str(a['servedProvider']))}"
                          f"</span> <code>{html.escape(str(a['servedModel']))}</code>")
            else:
                served = "-"
            body.append(
                f"<tr><td>{html.escape(a['title'])}</td>"
                f"<td><span class='pill {a['tier']}'>{a['tier']}</span></td>"
                f"<td><code>{html.escape(str(a['draftModel']))}</code></td>"
                f"<td><code>{html.escape(str(a['judgeModel']))}</code></td>"
                f"<td>{served}</td>"
                f"<td>{c}</td><td>{tok}</td></tr>"
            )
        rows.append(
            "<table><thead><tr><th>artifact</th><th>tier</th><th>draft model</th>"
            "<th>judge model</th><th>served by (actual)</th><th>cost</th><th>tokens</th>"
            "</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    run_note = (f" · run <code>{data['runId'][:8]}</code> · total "
                f"<span class='tot'>${data['totalCostUsd']:.4f}</span>"
                if data["runId"] else " · no run selected (showing the mapping only)")
    offline_banner = (
        "<div class='note'>Mode is <b>offline</b> → every stage actually runs on the "
        "<code>deterministic</code> provider ($0). The models below are what <b>live</b> "
        "mode would use.</div>" if data["mode"] != "live" else ""
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Model map · ANDS Forge OS</title><style>{_MODELS_CSS}</head><body>
<header><h1>Model map &amp; per-stage cost</h1>
<p>mode=<b>{data['mode']}</b> · effective provider: {data['effectiveProvider']} ·
configured providers: {', '.join(data['providers'])}{run_note}</p></header>
<main>
{offline_banner}
<div class='note'>Tiers — strong: <code>{html.escape(str(tiers['strong']))}</code> ·
cheap: <code>{html.escape(str(tiers['cheap']))}</code> ·
strong stages: {html.escape(', '.join(tiers['strongStages']) or '(none)')}.
Set per stage/artifact with <code>model:</code> in the blueprint, or via the
<code>FORGE_MODEL_STRONG</code> / <code>FORGE_MODEL_CHEAP</code> /
<code>FORGE_STRONG_STAGES</code> env vars.</div>
<div class='note'><b>Draft/judge model</b> = the model the tier <i>requests</i>.
<b>Served by (actual)</b> = the provider/model that actually answered — these differ when
the gateway falls back (e.g. Gemini 429 → <code>openai</code>/Groq). Append
<code>?run_id=&lt;id&gt;</code> (or open this from a run) to populate the served column.</div>
{''.join(rows)}
<p><a href='/'>&larr; back to runs</a> · <a href='/models'>raw JSON</a></p>
</main></body></html>"""


def _dashboard_html() -> str:
    rows = []
    for run_id in forge.store.list_runs():
        run = forge.get(run_id)
        pending = run.pending_gate["stage"] if run.pending_gate else "-"
        actions = ""
        if str(run.status) == "awaiting_approval":
            actions = (
                f"<button onclick=\"act('{run_id}','approve')\">approve</button> "
                f"<button onclick=\"act('{run_id}','reject')\">reject</button>"
            )
        mock = (
            f"<a href='/runs/{run_id}/mockup' target='_blank'>mockup</a>"
            if (forge.store.artifacts_dir(run_id) / 'ux' / 'mockup.html').exists() else "-"
        )
        rows.append(
            f"<tr><td>{run_id[:8]}</td><td>{html.escape(run.vision[:60])}</td>"
            f"<td><span class='s {run.status}'>{run.status}</span></td>"
            f"<td>{pending}</td><td>${run.cost_usd:.4f}</td><td>{mock}</td>"
            f"<td>{actions} <a href='/runs/{run_id}' target='_blank'>json</a> "
            f"<a href='/runs/{run_id}/audit' target='_blank'>audit</a> "
            f"<a href='/models/view?run_id={run_id}'>models</a></td></tr>"
        )
    body = "".join(rows) or "<tr><td colspan=7>No runs yet — POST /runs {vision}</td></tr>"
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>ANDS Forge OS</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#0f1221;color:#e7e9f5}}
header{{padding:20px 32px;border-bottom:1px solid #2a3158;background:#171a30}}
h1{{margin:0;font-size:20px}} p{{color:#9aa3c7;margin:4px 0 0}}
main{{padding:24px 32px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #2a3158}}
th{{color:#9aa3c7;font-weight:600}}
.s{{padding:2px 8px;border-radius:999px;font-size:12px}}
.awaiting_approval{{background:#7a5b16;color:#ffd479}}
.completed{{background:#1c4a2a;color:#7ee2a8}}
.running{{background:#1a3a5a;color:#7cc4ff}}
.rejected,.budget_exceeded,.failed{{background:#5a1a26;color:#ff9aae}}
button{{background:#7c5cff;color:#fff;border:0;border-radius:8px;padding:5px 10px;cursor:pointer}}
.bar{{margin-bottom:16px;display:flex;gap:8px}}
input{{flex:1;background:#1a1f3a;border:1px solid #2a3158;color:#e7e9f5;
       border-radius:8px;padding:8px}}
a{{color:#7cc4ff}}
</style></head><body>
<header><h1>ANDS Forge OS</h1>
<p>Autonomous product-development OS · offline-deterministic ·
{forge.blueprint.name} v{forge.blueprint.version} ·
<a href='/models/view'>model map</a></p></header>
<main>
<div class='bar'>
  <input id='vision' placeholder='State a product vision and press Start...'/>
  <button onclick='start()'>Start run</button>
</div>
<table><thead><tr><th>run</th><th>vision</th><th>status</th><th>pending gate</th>
<th>cost</th><th>mockup</th><th>actions</th></tr></thead>
<tbody>{body}</tbody></table>
</main>
<script>
async function start(){{
  const v=document.getElementById('vision').value;
  if(!v) return;
  await fetch('/runs',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{vision:v}})}});
  location.reload();
}}
async function act(id,what){{
  await fetch(`/runs/${{id}}/${{what}}`,{{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{feedback:'via dashboard'}})}});
  location.reload();
}}
</script>
</body></html>"""
