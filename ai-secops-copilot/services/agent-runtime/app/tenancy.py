"""Per-tenant isolation (Day 15, ADR-017).

Each tenant gets its **own** runtime state so one customer can never see another's
findings, approvals, tickets, audit trail, or LLM cost/cache:

  * ``state``        — audit trail, approvals, escalations, dead-letter (per-tenant
                       stores; for the SQLite backend each tenant gets its own file).
  * ``provider``     — ticket provider instance (idempotency + mock tickets per tenant).
  * ``gateway``      — AI Gateway instance (semantic cache + cost metrics per tenant).
  * ``graph_runner`` — compiled LangGraph with a per-tenant checkpointer.

Shared (safely): the read-only RAG knowledge corpus (same OWASP/CWE for everyone) and the
process-wide observability tracer/time-series (operator telemetry across tenants).

Contexts are built lazily and cached. The default offline backend is in-memory, so each
tenant simply gets independent objects; durable SQLite is namespaced per tenant by file.
"""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .gateway import Gateway, build_gateway
from .notifications import NotificationCenter, build_notification_center
from .persistence import build_state, get_checkpointer
from .policy import PolicyEngine, build_engine
from .providers import get_ticket_provider


def _scope_settings(settings: Settings, tenant_id: str) -> Settings:
    """Derive tenant-scoped settings for durable backends.

    SQLite is namespaced by inserting the tenant into the filename so each tenant has an
    isolated database file. In-memory needs no scoping (independent objects per build).
    Postgres keeps a single DSN here (production isolation is a tenant column / schema —
    out of scope for this increment); documented in ADR-017.
    """
    if settings.persistence_backend == "sqlite":
        path = Path(settings.sqlite_path or "var/secops.db")
        scoped = path.with_name(f"{path.stem}.{tenant_id}{path.suffix or '.db'}")
        return dataclasses.replace(settings, database_url=f"sqlite:///{scoped.as_posix()}")
    return settings


@dataclass
class TenantContext:
    """All per-tenant runtime state."""

    tenant_id: str
    state: Any  # StateStores
    provider: Any  # TicketProvider
    gateway: Gateway
    graph_runner: Any  # GraphRunner | None
    notifications: NotificationCenter
    policy: PolicyEngine

    @property
    def approvals(self) -> Any:
        return self.state.approvals

    @property
    def escalations(self) -> Any:
        return self.state.escalations

    @property
    def dead_letter(self) -> Any:
        return self.state.dead_letter

    @property
    def audit(self) -> Any:
        return self.state.audit


def _build_graph_runner(settings: Settings, context_stores: TenantContext) -> Any | None:
    """Compile a LangGraph runner bound to this tenant's provider + stores."""
    try:
        from .graph import GraphRunner

        return GraphRunner(
            provider=context_stores.provider,
            approvals=context_stores.approvals,
            escalations=context_stores.escalations,
            dead_letter=context_stores.dead_letter,
            checkpointer=get_checkpointer(settings),
        )
    except Exception:  # noqa: BLE001 - graph is optional; inline pipeline still works
        return None


class TenantRegistry:
    """Lazily builds and caches one :class:`TenantContext` per tenant id."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._contexts: dict[str, TenantContext] = {}
        self._lock = threading.Lock()

    def _build(self, tenant_id: str) -> TenantContext:
        scoped = _scope_settings(self._settings, tenant_id)
        ctx = TenantContext(
            tenant_id=tenant_id,
            state=build_state(scoped),
            provider=get_ticket_provider(scoped),
            gateway=build_gateway(scoped),
            graph_runner=None,
            notifications=build_notification_center(scoped),
            policy=build_engine(scoped, tenant_id),
        )
        ctx.graph_runner = _build_graph_runner(scoped, ctx)
        return ctx

    def get(self, tenant_id: str) -> TenantContext:
        with self._lock:
            ctx = self._contexts.get(tenant_id)
            if ctx is None:
                ctx = self._build(tenant_id)
                self._contexts[tenant_id] = ctx
            return ctx

    def reset(self, tenant_id: str) -> TenantContext:
        """Rebuild a tenant's context from scratch (used by ``POST /demo/reset``).

        Truncates durable stores in place first so SQLite/Postgres files are cleared
        (a fresh in-memory build alone would leave a durable file populated).
        """
        with self._lock:
            existing = self._contexts.get(tenant_id)
            if existing is not None:
                existing.state.clear()
                if hasattr(existing.provider, "clear"):
                    existing.provider.clear()
            ctx = self._build(tenant_id)
            self._contexts[tenant_id] = ctx
            return ctx

    def ids(self) -> list[str]:
        with self._lock:
            return sorted(self._contexts)
