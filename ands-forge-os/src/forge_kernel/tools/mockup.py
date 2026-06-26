"""render_mockup — turn a UX spec into ONE real, previewable HTML mockup.

The MVP demo requires "one real mockup rendered as HTML" (PRODUCT_VISION §12). This tool
takes a small, structured spec (title, personas, screens with sections/CTAs) and emits a
self-contained, styled HTML file with no external assets — so it previews instantly in a
browser or the dashboard. Deterministic output for reproducible demos.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .base import safe_join

_CSS = """
:root { --bg:#0f1221; --card:#1a1f3a; --ink:#e7e9f5; --muted:#9aa3c7; --accent:#7c5cff; }
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       background:var(--bg); color:var(--ink); }
header { padding:28px 40px; border-bottom:1px solid #2a3158;
         background:linear-gradient(120deg,#171a30,#211a40); }
header h1 { margin:0 0 6px; font-size:24px; }
header p { margin:0; color:var(--muted); }
.badge { display:inline-block; font-size:12px; color:var(--accent); border:1px solid var(--accent);
         border-radius:999px; padding:2px 10px; margin-bottom:10px; }
main { padding:32px 40px; display:grid; gap:24px; }
.personas { display:flex; gap:16px; flex-wrap:wrap; }
.persona { background:var(--card); border:1px solid #2a3158; border-radius:14px; padding:16px;
           min-width:220px; flex:1; }
.persona h3 { margin:0 0 6px; font-size:15px; }
.persona p { margin:0; color:var(--muted); font-size:13px; }
.screens { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:20px; }
.screen { background:var(--card); border:1px solid #2a3158; border-radius:16px; overflow:hidden; }
.screen .bar { background:#11142a; padding:10px 14px; font-size:13px; color:var(--muted);
               border-bottom:1px solid #2a3158; }
.screen .body { padding:18px; display:grid; gap:12px; }
.section { background:#222748; border:1px dashed #3a4170; border-radius:10px; padding:12px;
           font-size:13px; color:var(--ink); }
.cta { display:inline-block; background:var(--accent); color:#fff; border:none; border-radius:10px;
       padding:10px 16px; font-weight:600; font-size:13px; }
footer { padding:18px 40px; color:var(--muted); font-size:12px; border-top:1px solid #2a3158; }
"""


def _persona_html(p: dict) -> str:
    name = html.escape(str(p.get("name", "Persona")))
    desc = html.escape(str(p.get("goal", p.get("description", ""))))
    return f'<div class="persona"><h3>{name}</h3><p>{desc}</p></div>'


def _screen_html(s: dict) -> str:
    title = html.escape(str(s.get("name", "Screen")))
    sections = "".join(
        f'<div class="section">{html.escape(str(sec))}</div>'
        for sec in (s.get("sections") or [])
    )
    cta = s.get("cta")
    cta_html = f'<button class="cta">{html.escape(str(cta))}</button>' if cta else ""
    return (
        f'<div class="screen"><div class="bar">&#9679; {title}</div>'
        f'<div class="body">{sections}{cta_html}</div></div>'
    )


class RenderMockupTool:
    name = "render_mockup"

    def invoke(
        self,
        root: Path,
        *,
        title: str,
        path: str = "ux/mockup.html",
        subtitle: str = "",
        personas: list[dict] | None = None,
        screens: list[dict] | None = None,
        **_: Any,
    ) -> dict:
        personas = personas or []
        screens = screens or []
        personas_html = "".join(_persona_html(p) for p in personas) or (
            '<div class="persona"><p>No personas provided.</p></div>'
        )
        screens_html = "".join(_screen_html(s) for s in screens) or (
            '<div class="screen"><div class="bar">Screen</div>'
            '<div class="body"><div class="section">No screens provided.</div></div></div>'
        )
        doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — mockup</title>
<style>{_CSS}</style></head>
<body>
<header>
  <div class="badge">ANDS Forge OS · UX mockup</div>
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(subtitle)}</p>
</header>
<main>
  <section>
    <h2>Personas</h2>
    <div class="personas">{personas_html}</div>
  </section>
  <section>
    <h2>Key screens &amp; flows</h2>
    <div class="screens">{screens_html}</div>
  </section>
</main>
<footer>Rendered deterministically by the Forge kernel render_mockup tool.</footer>
</body></html>
"""
        target = safe_join(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc, encoding="utf-8")
        return {
            "tool": self.name,
            "path": str(target.relative_to(root.resolve())),
            "screens": len(screens),
            "personas": len(personas),
        }
