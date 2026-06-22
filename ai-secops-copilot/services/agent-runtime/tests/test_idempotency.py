"""Tests for finding_hash idempotency key derivation."""

from app.idempotency import finding_hash

_FINDING = {
    "id": "F-001",
    "ruleId": "python.lang.security.audit.formatted-sql-query",
    "file": "app/api/users.py",
    "startLine": 42,
    "cwe": "CWE-89",
}


def test_hash_is_stable():
    assert finding_hash(_FINDING) == finding_hash(dict(_FINDING))


def test_hash_ignores_volatile_fields():
    a = dict(_FINDING, message="changed message text", scannerSeverity="WARNING")
    assert finding_hash(a) == finding_hash(_FINDING)


def test_hash_changes_with_identity():
    a = dict(_FINDING, startLine=99)
    assert finding_hash(a) != finding_hash(_FINDING)


def test_hash_is_hex_32_chars():
    h = finding_hash(_FINDING)
    assert len(h) == 32
    int(h, 16)  # parseable as hex
