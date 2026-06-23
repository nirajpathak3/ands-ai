"""Scanner-report ingestion: normalize Semgrep / SARIF to the finding contract.

The Copilot ingests findings (it is not a scanner). These adapters map a raw
scanner report to a list of normalized findings (``schemas.Finding`` shape) that
the pipeline can analyze.
"""

from __future__ import annotations

from typing import Any

from .sarif import normalize_sarif
from .semgrep import normalize_semgrep

__all__ = ["normalize_semgrep", "normalize_sarif", "detect_format", "normalize"]


def detect_format(report: dict[str, Any]) -> str:
    """Best-effort format detection for a parsed scanner report."""
    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    if "runs" in report:
        return "sarif"
    if "results" in report:
        return "semgrep"
    raise ValueError(
        "Unrecognized report: expected Semgrep ('results') or SARIF ('runs') JSON."
    )


def normalize(report: dict[str, Any], fmt: str = "auto") -> list[dict]:
    """Normalize a scanner report to findings, auto-detecting the format if needed."""
    chosen = detect_format(report) if fmt == "auto" else fmt.lower()
    if chosen == "semgrep":
        return normalize_semgrep(report)
    if chosen == "sarif":
        return normalize_sarif(report)
    raise ValueError(f"Unknown report format: {fmt!r} (use auto | semgrep | sarif)")
