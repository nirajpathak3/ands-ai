"""Tests for the Day-10 persistence seam: durable SQLite stores + factory selection."""

import os
from dataclasses import dataclass

from app.config import Settings
from app.persistence import build_state, get_checkpointer
from app.persistence.sqlite_store import SqliteState

DECISION = {
    "findingId": "F-1", "findingHash": "abc123", "disposition": "human_approval",
    "reasonCode": "approval_band",
    "analysis": {"severity": "medium", "confidence": 0.78, "recommendedAction": "create_ticket"},
}


@dataclass
class _FakeTicket:
    key: str = "SEC-9"
    provider: str = "mock"
    status: str = "open"

    def to_dict(self):
        return {"key": self.key, "provider": self.provider, "status": self.status}


class _FakeProvider:
    name = "fake"

    def create(self, decision, *, via="auto"):
        return _FakeTicket(), True


# --- durability across reconnects -------------------------------------------

def test_sqlite_audit_survives_reopen(tmp_path):
    db = str(tmp_path / "state.db")
    SqliteState(db).audit.record(DECISION, "ticket_created", actor="system", latency_ms=1.2)

    # A fresh connection (simulating a process restart) still sees the record.
    records = SqliteState(db).audit.list_all()
    assert len(records) == 1
    assert records[0].findingId == "F-1"
    assert records[0].outcome == "ticket_created"
    assert records[0].latencyMs == 1.2


def test_sqlite_approvals_persist_and_approve(tmp_path):
    db = str(tmp_path / "state.db")
    SqliteState(db).approvals.enqueue(DECISION)

    reopened = SqliteState(db).approvals
    assert len(reopened.list_pending()) == 1
    ticket, created = reopened.approve("abc123", _FakeProvider())
    assert created is True
    assert reopened.get("abc123") is None  # dequeued after approval


def test_sqlite_escalation_idempotent(tmp_path):
    db = str(tmp_path / "state.db")
    q = SqliteState(db).escalations
    q.add(DECISION)
    q.add(DECISION)  # same finding_hash -> updated in place, not duplicated
    assert len(q.list_all()) == 1


def test_sqlite_dead_letter_appends(tmp_path):
    db = str(tmp_path / "state.db")
    dl = SqliteState(db).dead_letter
    dl.add(DECISION, "Jira 503")
    items = SqliteState(db).dead_letter.list_all()
    assert len(items) == 1 and items[0].error == "Jira 503"


# --- factory selection ------------------------------------------------------

def test_build_state_defaults_to_memory():
    state = build_state(Settings(database_url=""))
    assert state.backend == "memory"


def test_build_state_uses_sqlite(tmp_path):
    db = f"sqlite:///{tmp_path / 'f.db'}"
    state = build_state(Settings(database_url=db))
    assert state.backend == "sqlite"
    state.audit.record(DECISION, "escalated")
    assert len(state.audit.list_all()) == 1
    state.clear()
    assert state.audit.list_all() == []


def test_get_checkpointer_returns_saver():
    # langgraph is installed in this env -> MemorySaver fallback is returned.
    assert get_checkpointer(Settings(database_url="")) is not None


def test_persistence_backend_derivation():
    assert Settings(database_url="").persistence_backend == "memory"
    assert Settings(database_url="sqlite:///x.db").persistence_backend == "sqlite"
    assert Settings(database_url="postgresql://localhost/db").persistence_backend == "postgres"


def test_env_database_url_round_trips(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///var/secops.db")
    assert os.environ["DATABASE_URL"] == "sqlite:///var/secops.db"
