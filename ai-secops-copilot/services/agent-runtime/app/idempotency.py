"""Idempotency key derivation for findings (ADR-009).

A stable ``finding_hash`` derived from the identity of a finding lets ticket
creation be idempotent: retries / at-least-once delivery must not open duplicate
tickets. Pure stdlib so it is testable in isolation.
"""

from __future__ import annotations

import hashlib
from typing import Mapping


def finding_hash(finding: Mapping[str, object]) -> str:
    """Derive a stable idempotency key from a finding's identity.

    Identity = (ruleId, file, startLine, cwe). We deliberately exclude volatile
    fields (message text, scanner version) so cosmetic changes do not produce a
    new key and re-open a duplicate ticket.
    """
    parts = [
        str(finding.get("ruleId", "")),
        str(finding.get("file", "")),
        str(finding.get("startLine", "")),
        str(finding.get("cwe", "")),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]
