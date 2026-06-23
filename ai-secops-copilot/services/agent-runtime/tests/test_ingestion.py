"""Tests for scanner-report ingestion (Semgrep + SARIF -> finding contract)."""

import json
from pathlib import Path

import pytest

from app.analysis import analyze_finding
from app.ingestion import detect_format, normalize, normalize_sarif, normalize_semgrep
from app.schemas import Finding

SAMPLES = Path(__file__).resolve().parents[3] / "datasets" / "samples"

_SEMGREP = {
    "results": [
        {
            "check_id": "python.lang.security.audit.formatted-sql-query.formatted-sql-query",
            "path": "app/api/users.py",
            "start": {"line": 42}, "end": {"line": 42},
            "extra": {
                "message": "user input in SQL",
                "severity": "ERROR",
                "lines": "query = '...' + request.args['name']; cursor.execute(query)",
                "metadata": {"cwe": ["CWE-89: SQL Injection"], "owasp": ["A03:2021 - Injection"]},
            },
        }
    ]
}

_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "semgrep", "rules": [
                {"id": "cmd-inj", "name": "Command injection",
                 "properties": {"tags": ["CWE-78"]},
                 "defaultConfiguration": {"level": "error"}},
            ]}},
            "results": [
                {
                    "ruleId": "cmd-inj",
                    "message": {"text": "shell=True with user input"},
                    "locations": [{"physicalLocation": {
                        "artifactLocation": {"uri": "app/services/exporter.py"},
                        "region": {
                            "startLine": 88, "endLine": 88,
                            "snippet": {"text": "subprocess.run(cmd + user_path, shell=True)"},
                        },
                    }}],
                }
            ],
        }
    ],
}


def test_semgrep_field_mapping():
    findings = normalize_semgrep(_SEMGREP)
    assert len(findings) == 1
    f = findings[0]
    assert f["scanner"] == "semgrep"
    assert f["ruleId"].endswith("formatted-sql-query")
    assert f["file"] == "app/api/users.py"
    assert f["startLine"] == 42
    assert f["cwe"] == "CWE-89"
    assert f["owasp"] == "A03:2021-Injection"
    assert f["scannerSeverity"] == "ERROR"
    assert f["codeSnippet"]
    assert f["id"].startswith("sg-")
    Finding.model_validate(f)  # conforms to the contract


def test_sarif_field_mapping():
    findings = normalize_sarif(_SARIF)
    assert len(findings) == 1
    f = findings[0]
    assert f["scanner"] == "semgrep"
    assert f["ruleId"] == "cmd-inj"
    assert f["file"] == "app/services/exporter.py"
    assert f["cwe"] == "CWE-78"
    assert f["scannerSeverity"] == "ERROR"
    assert f["id"].startswith("sarif-")
    Finding.model_validate(f)


def test_detect_format():
    assert detect_format(_SEMGREP) == "semgrep"
    assert detect_format(_SARIF) == "sarif"
    with pytest.raises(ValueError):
        detect_format({"nope": 1})


def test_normalize_auto_dispatches():
    assert len(normalize(_SEMGREP)) == 1
    assert len(normalize(_SARIF)) == 1


def test_sample_files_parse_and_drive_expected_actions():
    semgrep = json.loads((SAMPLES / "semgrep-sample.json").read_text(encoding="utf-8"))
    findings = normalize(semgrep)
    by_file = {f["file"]: analyze_finding(f)["recommendedAction"] for f in findings}
    assert by_file["app/api/users.py"] == "create_ticket"      # real SQLi
    assert by_file["app/cache/keys.py"] == "suppress"          # md5 cache key FP
    assert by_file["app/clients/partner.py"] == "create_ticket"  # cleartext http
    assert by_file["app/workers/consumer.py"] == "escalate"    # pickle, ambiguous source


def test_sarif_sample_drives_expected_actions():
    sarif = json.loads((SAMPLES / "sarif-sample.json").read_text(encoding="utf-8"))
    findings = normalize(sarif)
    by_file = {f["file"]: analyze_finding(f)["recommendedAction"] for f in findings}
    assert by_file["app/services/exporter.py"] == "create_ticket"   # shell=True + user input
    assert by_file["app/services/healthcheck.py"] == "suppress"     # shell=False, fixed args
