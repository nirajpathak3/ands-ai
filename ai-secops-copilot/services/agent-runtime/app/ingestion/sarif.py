"""SARIF v2.1.0 -> normalized finding contract (ADR-007).

SARIF (OASIS standard) is the vendor-neutral interchange format emitted by many
scanners. We read the common shape:

    runs[].tool.driver.{name, rules[]}
    runs[].results[].{ruleId, level, message.text,
                      locations[].physicalLocation.{artifactLocation.uri,
                                                    region.{startLine,endLine,snippet.text}}}

CWE/OWASP are pulled from the rule's (or result's) ``properties.tags``. Missing
fields degrade gracefully so partial/odd SARIF still ingests.
"""

from __future__ import annotations

from typing import Any

from .common import (
    extract_cwe,
    extract_owasp,
    normalize_severity,
    stable_id,
)


def _rule_index(driver: dict[str, Any]) -> dict[str, dict]:
    return {r.get("id"): r for r in (driver.get("rules") or []) if r.get("id")}


def normalize_sarif(report: dict[str, Any]) -> list[dict]:
    findings: list[dict] = []
    for run in report.get("runs", []) or []:
        driver = (run.get("tool", {}) or {}).get("driver", {}) or {}
        scanner = driver.get("name", "sarif") or "sarif"
        rules = _rule_index(driver)

        for result in run.get("results", []) or []:
            rule_id = result.get("ruleId") or ""
            rule = rules.get(rule_id, {}) or {}

            level = (
                result.get("level")
                or (rule.get("defaultConfiguration", {}) or {}).get("level")
                or "warning"
            )

            message = (result.get("message", {}) or {}).get("text", "") or ""

            locations = result.get("locations") or []
            phys = (locations[0].get("physicalLocation", {}) if locations else {}) or {}
            uri = (phys.get("artifactLocation", {}) or {}).get("uri", "") or ""
            region = phys.get("region", {}) or {}
            snippet = (region.get("snippet", {}) or {}).get("text")

            tags = list((rule.get("properties", {}) or {}).get("tags", []) or [])
            tags += list((result.get("properties", {}) or {}).get("tags", []) or [])

            title = (
                rule.get("name")
                or (rule.get("shortDescription", {}) or {}).get("text")
                or rule_id
                or "Finding"
            )

            start_line = region.get("startLine")
            findings.append({
                "id": stable_id("sarif", rule_id, uri, start_line),
                "scanner": scanner,
                "ruleId": rule_id,
                "title": title,
                "message": message,
                "file": uri,
                "startLine": start_line,
                "endLine": region.get("endLine"),
                "codeSnippet": snippet,
                "cwe": extract_cwe(tags) or extract_cwe(rule_id),
                "owasp": extract_owasp(tags),
                "scannerSeverity": normalize_severity(level),
            })
    return findings
