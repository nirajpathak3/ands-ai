"""Semgrep JSON output -> normalized finding contract (ADR-007).

Parses the public Semgrep JSON format (``semgrep --json``):

    {"results": [{"check_id", "path", "start": {"line"}, "end": {"line"},
                  "extra": {"message", "severity", "lines",
                            "metadata": {"cwe": [...], "owasp": [...]}}}],
     "errors": [...]}

We ingest this output — we do **not** run Semgrep (the product triages findings,
it is not a scanner). Unknown/missing fields degrade gracefully.
"""

from __future__ import annotations

from typing import Any

from .common import (
    extract_cwe,
    extract_owasp,
    normalize_severity,
    rule_leaf_title,
    stable_id,
)


def normalize_semgrep(report: dict[str, Any]) -> list[dict]:
    findings: list[dict] = []
    for result in report.get("results", []) or []:
        check_id = result.get("check_id", "") or ""
        path = result.get("path", "") or ""
        start = result.get("start", {}) or {}
        end = result.get("end", {}) or {}
        extra = result.get("extra", {}) or {}
        meta = extra.get("metadata", {}) or {}

        start_line = start.get("line")
        findings.append({
            "id": stable_id("sg", check_id, path, start_line),
            "scanner": "semgrep",
            "ruleId": check_id,
            "title": rule_leaf_title(check_id),
            "message": extra.get("message", "") or "",
            "file": path,
            "startLine": start_line,
            "endLine": end.get("line"),
            "codeSnippet": extra.get("lines") or None,
            "cwe": extract_cwe(meta.get("cwe")),
            "owasp": extract_owasp(meta.get("owasp")),
            "scannerSeverity": normalize_severity(extra.get("severity")),
        })
    return findings
