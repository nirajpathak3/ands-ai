"""Durable state stores backed by stdlib ``sqlite3`` (Day 10).

These are drop-in replacements for the in-memory stores in ``app/ticketing.py`` — same
method signatures — so approvals, escalations, dead-letters, and the audit trail survive
a process restart. SQLite is the offline/CI-testable durable backend; the production
target is Postgres with the identical schema (``infra/postgres/state.sql``).

Stdlib only: a single connection (``check_same_thread=False`` + a lock) is plenty for the
runtime's modest, low-concurrency write rate.
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path

from ..ticketing import (
    AuditRecord,
    DeadLetterItem,
    PendingApproval,
    Ticket,
    TicketProvider,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    finding_hash TEXT NOT NULL,
    finding_id TEXT,
    severity TEXT,
    recommended_action TEXT,
    confidence REAL,
    disposition TEXT,
    reason_code TEXT,
    outcome TEXT,
    actor TEXT,
    latency_ms REAL
);
CREATE TABLE IF NOT EXISTS approvals (
    finding_hash TEXT PRIMARY KEY,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS escalations (
    finding_hash TEXT PRIMARY KEY,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dead_letter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_hash TEXT NOT NULL,
    error TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _utcnow() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def _analysis(decision: Mapping[str, object]) -> Mapping:
    analysis = decision.get("analysis") or {}
    return analysis if isinstance(analysis, Mapping) else {}


class SqliteState:
    """Opens (and migrates) the SQLite database and exposes the four stores."""

    def __init__(self, path: str) -> None:
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.isolation_level = None  # autocommit
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)

        self.audit = SqliteAuditLog(self._conn, self._lock)
        self.approvals = SqliteApprovalStore(self._conn, self._lock)
        self.escalations = SqliteEscalationQueue(self._conn, self._lock)
        self.dead_letter = SqliteDeadLetterQueue(self._conn, self._lock)


class _Base:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self._conn = conn
        self._lock = lock


class SqliteAuditLog(_Base):
    def record(
        self,
        decision: Mapping[str, object],
        outcome: str,
        *,
        actor: str = "system",
        latency_ms: float = 0.0,
    ) -> AuditRecord:
        analysis = _analysis(decision)
        rec = AuditRecord(
            timestamp=_utcnow(),
            findingHash=str(decision.get("findingHash", "")),
            findingId=(str(decision["findingId"]) if decision.get("findingId") else None),
            severity=str(analysis.get("severity", "unknown")),
            recommendedAction=str(analysis.get("recommendedAction", "")),
            confidence=float(analysis.get("confidence", 0.0) or 0.0),
            disposition=str(decision.get("disposition", "")),
            reasonCode=(str(decision["reasonCode"]) if decision.get("reasonCode") else None),
            outcome=outcome,
            actor=actor,
            latencyMs=round(float(latency_ms), 2),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit (timestamp, finding_hash, finding_id, severity, "
                "recommended_action, confidence, disposition, reason_code, outcome, "
                "actor, latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rec.timestamp, rec.findingHash, rec.findingId, rec.severity,
                 rec.recommendedAction, rec.confidence, rec.disposition, rec.reasonCode,
                 rec.outcome, rec.actor, rec.latencyMs),
            )
        return rec

    def list_all(self) -> list[AuditRecord]:
        rows = self._conn.execute("SELECT * FROM audit ORDER BY id ASC").fetchall()
        return [
            AuditRecord(
                timestamp=r["timestamp"], findingHash=r["finding_hash"],
                findingId=r["finding_id"], severity=r["severity"],
                recommendedAction=r["recommended_action"], confidence=r["confidence"],
                disposition=r["disposition"], reasonCode=r["reason_code"],
                outcome=r["outcome"], actor=r["actor"], latencyMs=r["latency_ms"],
            )
            for r in rows
        ]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM audit")


class SqliteApprovalStore(_Base):
    def enqueue(self, decision: Mapping[str, object]) -> PendingApproval:
        finding_hash = str(decision.get("findingHash", ""))
        with self._lock:
            self._conn.execute(
                "INSERT INTO approvals (finding_hash, decision_json, created_at) "
                "VALUES (?,?,?) ON CONFLICT(finding_hash) DO UPDATE SET "
                "decision_json=excluded.decision_json",
                (finding_hash, json.dumps(dict(decision)), _utcnow()),
            )
        return PendingApproval(findingHash=finding_hash, decision=dict(decision))

    def list_pending(self) -> list[PendingApproval]:
        rows = self._conn.execute(
            "SELECT finding_hash, decision_json FROM approvals ORDER BY created_at ASC"
        ).fetchall()
        return [
            PendingApproval(findingHash=r["finding_hash"], decision=json.loads(r["decision_json"]))
            for r in rows
        ]

    def get(self, finding_hash: str) -> PendingApproval | None:
        row = self._conn.execute(
            "SELECT decision_json FROM approvals WHERE finding_hash=?", (finding_hash,)
        ).fetchone()
        if row is None:
            return None
        return PendingApproval(findingHash=finding_hash, decision=json.loads(row["decision_json"]))

    def approve(self, finding_hash: str, provider: TicketProvider) -> tuple[Ticket, bool]:
        item = self.get(finding_hash)
        if item is None:
            raise KeyError(finding_hash)
        ticket, created = provider.create(item.decision, via="approval")
        with self._lock:
            self._conn.execute("DELETE FROM approvals WHERE finding_hash=?", (finding_hash,))
        return ticket, created

    def reject(self, finding_hash: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM approvals WHERE finding_hash=?", (finding_hash,)
            )
        return cur.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM approvals")


class SqliteEscalationQueue(_Base):
    def add(self, decision: Mapping[str, object]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO escalations (finding_hash, decision_json, created_at) "
                "VALUES (?,?,?) ON CONFLICT(finding_hash) DO UPDATE SET "
                "decision_json=excluded.decision_json",
                (str(decision.get("findingHash", "")), json.dumps(dict(decision)), _utcnow()),
            )

    def list_all(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT decision_json FROM escalations ORDER BY created_at ASC"
        ).fetchall()
        return [json.loads(r["decision_json"]) for r in rows]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM escalations")


class SqliteDeadLetterQueue(_Base):
    def add(self, decision: Mapping[str, object], error: str) -> DeadLetterItem:
        finding_hash = str(decision.get("findingHash", ""))
        with self._lock:
            self._conn.execute(
                "INSERT INTO dead_letter (finding_hash, error, decision_json, created_at) "
                "VALUES (?,?,?,?)",
                (finding_hash, error, json.dumps(dict(decision)), _utcnow()),
            )
        return DeadLetterItem(findingHash=finding_hash, error=error, decision=dict(decision))

    def list_all(self) -> list[DeadLetterItem]:
        rows = self._conn.execute(
            "SELECT finding_hash, error, decision_json FROM dead_letter ORDER BY id ASC"
        ).fetchall()
        return [
            DeadLetterItem(
                findingHash=r["finding_hash"], error=r["error"],
                decision=json.loads(r["decision_json"]),
            )
            for r in rows
        ]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM dead_letter")
