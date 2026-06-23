"""Persistence seam (Day 10): pluggable durable state + graph checkpointer.

Backends are selected from ``Settings.persistence_backend`` (derived from DATABASE_URL):

  * ``memory``   - in-memory stores (offline default).
  * ``sqlite``   - durable stdlib-sqlite stores (local/CI durability).
  * ``postgres`` - production target; same SQL schema (``infra/postgres/state.sql``).

Everything degrades gracefully: an unavailable durable backend falls back to memory so
the runtime always starts. The same seam upgrades the LangGraph checkpointer from the
in-memory ``MemorySaver`` to a Postgres/SQLite saver when the optional package is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..ticketing import ApprovalStore, AuditLog, DeadLetterQueue, EscalationQueue


@dataclass
class StateStores:
    """The runtime's durable state, regardless of backend."""

    approvals: Any
    escalations: Any
    dead_letter: Any
    audit: Any
    backend: str

    def clear(self) -> None:
        """Reset all stores (demo reset / tests) — works for any backend."""
        self.approvals.clear()
        self.escalations.clear()
        self.dead_letter.clear()
        self.audit.clear()


def build_state(settings: Settings) -> StateStores:
    """Construct the state stores for the configured backend (falls back to memory)."""
    backend = settings.persistence_backend
    if backend == "sqlite":
        from .sqlite_store import SqliteState

        state = SqliteState(settings.sqlite_path or "var/secops.db")
        return StateStores(
            approvals=state.approvals, escalations=state.escalations,
            dead_letter=state.dead_letter, audit=state.audit, backend="sqlite",
        )
    if backend == "postgres":
        try:
            from .postgres_store import PostgresState  # optional (psycopg)

            state = PostgresState(settings.database_url)
            return StateStores(
                approvals=state.approvals, escalations=state.escalations,
                dead_letter=state.dead_letter, audit=state.audit, backend="postgres",
            )
        except Exception:  # noqa: BLE001 - psycopg not installed -> degrade to memory
            pass

    return StateStores(
        approvals=ApprovalStore(), escalations=EscalationQueue(),
        dead_letter=DeadLetterQueue(), audit=AuditLog(), backend="memory",
    )


def get_checkpointer(settings: Settings) -> Any | None:
    """Return a LangGraph checkpointer for the configured backend.

    Prefers a durable saver (Postgres/SQLite) when its optional package is installed and
    DATABASE_URL is set; otherwise returns an in-memory ``MemorySaver``. Returns None only
    if LangGraph itself is missing (the inline pipeline is then used).
    """
    backend = settings.persistence_backend
    try:
        if backend == "postgres":
            try:
                from langgraph.checkpoint.postgres import PostgresSaver

                cm = PostgresSaver.from_conn_string(settings.database_url)
                saver = cm.__enter__()
                saver.setup()
                return saver
            except Exception:  # noqa: BLE001 - optional; fall through to memory
                pass
        if backend == "sqlite":
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver

                cm = SqliteSaver.from_conn_string(settings.sqlite_path or "var/secops.db")
                return cm.__enter__()
            except Exception:  # noqa: BLE001 - optional; fall through to memory
                pass
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except Exception:  # noqa: BLE001 - langgraph not installed
        return None
