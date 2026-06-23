"""Shared helpers for scanner-report ingestion (ADR-007).

Adapters normalize each scanner's native output into the common finding contract
(``schemas.Finding``): id, scanner, ruleId, title, message, file, startLine,
endLine, codeSnippet, cwe, owasp, scannerSeverity. These helpers extract the
public-standard bits (CWE, OWASP, severity) that scanners encode inconsistently.

Pure stdlib so the adapters are trivially testable.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_CWE_RE = re.compile(r"CWE-(\d+)", re.IGNORECASE)
_OWASP_RE = re.compile(r"A\d{2}:20\d{2}[^,\]\"']*")

# Normalize any scanner's level wording to our scale (ERROR | WARNING | INFO).
_LEVEL_TO_SCANNER_SEVERITY = {
    "error": "ERROR",
    "critical": "ERROR",
    "high": "ERROR",
    "warning": "WARNING",
    "medium": "WARNING",
    "moderate": "WARNING",
    "note": "INFO",
    "info": "INFO",
    "low": "INFO",
    "none": "INFO",
}


def _flatten(value: Any) -> str:
    """Collapse a str / list / nested structure to a single searchable string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    return str(value)


def extract_cwe(value: Any) -> str | None:
    """Return a normalized ``CWE-<n>`` from any string/list, else None."""
    match = _CWE_RE.search(_flatten(value))
    return f"CWE-{match.group(1)}" if match else None


def extract_owasp(value: Any) -> str | None:
    """Best-effort OWASP Top-10 category (e.g. ``A03:2021-...``), else None."""
    match = _OWASP_RE.search(_flatten(value))
    if not match:
        return None
    return match.group(0).strip().replace(" - ", "-").replace(" ", "")


def normalize_severity(level: Any) -> str:
    return _LEVEL_TO_SCANNER_SEVERITY.get(str(level or "").strip().lower(), "WARNING")


def rule_leaf_title(rule_id: str) -> str:
    """Human-ish title from a dotted rule id (Semgrep check_id has no title)."""
    leaf = (rule_id or "").split(".")[-1]
    words = re.split(r"[-_]+", leaf)
    return " ".join(w for w in words if w).strip().capitalize() or (rule_id or "Finding")


def stable_id(prefix: str, *parts: Any) -> str:
    """Deterministic short id from identifying parts (stable across runs)."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:10]}"
