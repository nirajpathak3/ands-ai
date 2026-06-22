"""Predictors for the evaluation harness.

A *predictor* takes a normalized finding (one record from the golden dataset)
and returns a triage prediction:

    {
        "severity": "info" | "low" | "medium" | "high" | "critical",
        "action":   "create_ticket" | "suppress" | "escalate",
        "confidence": float in [0, 1],
        "reason":   str,
    }

This mirrors the structured-output contract the Python agent-runtime will
emit (see services/agent-runtime/app/schemas.py). Day 1 ships a dependency-free
heuristic baseline so the eval harness is runnable immediately; later days swap
in the LangGraph/LLM predictor via the ``runtime`` predictor.

Clean-room: the CWE -> severity mapping below is derived from public MITRE CWE
and OWASP Top 10 risk guidance only.
"""

from __future__ import annotations

from typing import Callable, Dict

Prediction = Dict[str, object]
Finding = Dict[str, object]

SEVERITIES = ["info", "low", "medium", "high", "critical"]
ACTIONS = ["create_ticket", "suppress", "escalate"]

# CWE -> baseline severity, grounded in public CWE/OWASP risk guidance.
_CWE_SEVERITY: Dict[str, str] = {
    # Critical: unauthenticated RCE / full data compromise classes.
    "CWE-89": "critical",   # SQL Injection
    "CWE-78": "critical",   # OS Command Injection
    "CWE-94": "critical",   # Code Injection
    "CWE-502": "critical",  # Insecure Deserialization
    "CWE-79": "critical",   # Cross-site Scripting
    "CWE-611": "critical",  # XXE
    "CWE-918": "critical",  # SSRF
    "CWE-22": "critical",   # Path Traversal
    "CWE-798": "critical",  # Hardcoded Credentials
    # High: serious auth/crypto/access-control weaknesses.
    "CWE-327": "high",      # Broken/Risky Crypto
    "CWE-295": "high",      # Improper Certificate Validation
    "CWE-256": "high",      # Plaintext Password Storage
    "CWE-330": "high",      # Insufficient Randomness
    "CWE-434": "high",      # Unrestricted Upload
    "CWE-862": "high",      # Missing Authorization
    "CWE-863": "high",      # Incorrect Authorization
    "CWE-639": "high",      # IDOR
    "CWE-352": "high",      # CSRF
    "CWE-601": "high",      # Open Redirect
    "CWE-326": "high",      # Inadequate Encryption Strength
    "CWE-915": "high",      # Mass Assignment
    "CWE-1333": "high",     # ReDoS
    "CWE-209": "high",      # Sensitive Info in Error
    # Medium: misconfiguration / hardening gaps.
    "CWE-319": "medium",    # Cleartext Transmission
    "CWE-614": "medium",    # Sensitive Cookie without Secure
    "CWE-1004": "medium",   # Sensitive Cookie without HttpOnly
    "CWE-942": "medium",    # Permissive CORS
    "CWE-307": "medium",    # Improper Restriction of Auth Attempts
    "CWE-377": "medium",    # Insecure Temp File
    "CWE-117": "medium",    # Log Injection
    "CWE-521": "medium",    # Weak Password Requirements
    "CWE-200": "medium",    # Information Exposure
    "CWE-489": "medium",    # Active Debug Code
    "CWE-565": "medium",    # Reliance on Untrusted Cookie
    # Low: maintainability / correctness.
    "CWE-477": "low",       # Obsolete Function
    "CWE-547": "low",       # Hardcoded Constant
    "CWE-563": "low",       # Unused Variable
    "CWE-561": "low",       # Dead Code
    "CWE-1041": "low",      # Duplicate Code
    "CWE-252": "low",       # Unchecked Return Value
}

# Native scanner severity -> our scale (fallback when CWE is unknown).
_SCANNER_SEVERITY: Dict[str, str] = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}

_SEVERITY_CONFIDENCE: Dict[str, float] = {
    "critical": 0.95,
    "high": 0.85,
    "medium": 0.70,
    "low": 0.60,
    "info": 0.80,
}

# Weak path signal the heuristic uses to guess "this is probably a false
# positive" (e.g. test fixtures, docs/examples). Intentionally incomplete:
# the LLM+RAG predictor is expected to beat this on false-positive recall.
_FP_PATH_MARKERS = (
    "tests/",
    "/test/",
    "test_",
    "_test.",
    "/spec/",
    "examples/",
    "example/",
    "/docs/",
    "sample",
    "fixture",
)


def _looks_like_false_positive(file_path: str) -> bool:
    p = (file_path or "").lower()
    return any(marker in p for marker in _FP_PATH_MARKERS)


def heuristic_predictor(finding: Finding) -> Prediction:
    """Rule-based baseline: map CWE -> severity, weak path-based FP guess.

    Deliberately cannot reason about code semantics or trust boundaries, so it
    misses most false positives and never escalates. That gap is the baseline
    the LLM-backed predictor must improve on.
    """
    cwe = str(finding.get("cwe", ""))
    file_path = str(finding.get("file", ""))
    scanner_sev = str(finding.get("scannerSeverity", "INFO"))

    if _looks_like_false_positive(file_path):
        return {
            "severity": "info",
            "action": "suppress",
            "confidence": 0.65,
            "reason": f"Path '{file_path}' matches a test/docs/example location; likely a non-production false positive.",
        }

    severity = _CWE_SEVERITY.get(cwe) or _SCANNER_SEVERITY.get(scanner_sev, "low")

    if severity == "info":
        action = "suppress"
    else:
        action = "create_ticket"

    return {
        "severity": severity,
        "action": action,
        "confidence": _SEVERITY_CONFIDENCE.get(severity, 0.6),
        "reason": f"Baseline mapping of {cwe or scanner_sev} -> {severity}.",
    }


def _load_runtime_analyzer() -> Callable[[Finding], Dict[str, object]]:
    """Load the agent-runtime analysis core (pure stdlib) directly from its file.

    We import by path rather than installing the package so the eval harness keeps
    its zero-dependency, run-anywhere property. The analysis module is deliberately
    self-contained (no intra-package imports) so it loads in isolation.
    """
    import importlib.util
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    analysis_path = repo_root / "services" / "agent-runtime" / "app" / "analysis.py"
    if not analysis_path.exists():
        raise SystemExit(f"agent-runtime analysis core not found at {analysis_path}")

    spec = importlib.util.spec_from_file_location("agent_runtime_analysis", analysis_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load analysis core from {analysis_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.analyze_finding


_runtime_analyzer: Callable[[Finding], Dict[str, object]] | None = None


def runtime_predictor(finding: Finding) -> Prediction:
    """The agent-runtime predictor: the Finding Analysis Node's reasoning.

    Day 2 wires this to the same deterministic analysis core the LangGraph runtime
    uses (services/agent-runtime/app/analysis.py), so `--predictor runtime` measures
    the actual node logic offline. On Day 11 the AI Gateway swaps a real LLM in
    behind the node's LLMClient seam; this predictor then measures that model.
    """
    global _runtime_analyzer
    if _runtime_analyzer is None:
        _runtime_analyzer = _load_runtime_analyzer()

    analysis = _runtime_analyzer(finding)
    return {
        "severity": analysis["severity"],
        "action": analysis["recommendedAction"],
        "confidence": analysis["confidence"],
        "reason": analysis["reason"],
    }


_PREDICTORS: Dict[str, Callable[[Finding], Prediction]] = {
    "heuristic": heuristic_predictor,
    "runtime": runtime_predictor,
}


def get_predictor(name: str) -> Callable[[Finding], Prediction]:
    try:
        return _PREDICTORS[name]
    except KeyError:
        valid = ", ".join(sorted(_PREDICTORS))
        raise SystemExit(f"Unknown predictor '{name}'. Available: {valid}")


def available_predictors() -> list[str]:
    return sorted(_PREDICTORS)
