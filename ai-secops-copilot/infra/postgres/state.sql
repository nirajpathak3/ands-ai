-- Durable runtime-state schema (Day 10): audit trail, approvals, escalations,
-- dead-letter. This is the production (Postgres) target; the offline/CI default is
-- in-memory, and the SQLite backend (app/persistence/sqlite_store.py) uses the same
-- shape. Provisioned when DATABASE_URL points at Postgres.
--
-- The append-only audit trail is the compliance backbone (who/what/why per decision);
-- approvals/escalations are keyed by finding_hash for idempotency (ADR-009).

CREATE TABLE IF NOT EXISTS audit (
    id                 BIGSERIAL PRIMARY KEY,
    timestamp          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finding_hash       TEXT NOT NULL,
    finding_id         TEXT,
    severity           TEXT,
    recommended_action TEXT,
    confidence         REAL,
    disposition        TEXT,
    reason_code        TEXT,
    outcome            TEXT,
    actor              TEXT,                 -- "system" | "human"
    latency_ms         REAL
);
CREATE INDEX IF NOT EXISTS idx_audit_finding_hash ON audit (finding_hash);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit (timestamp);

CREATE TABLE IF NOT EXISTS approvals (
    finding_hash  TEXT PRIMARY KEY,          -- idempotent: one pending item per finding
    decision_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalations (
    finding_hash  TEXT PRIMARY KEY,          -- idempotent: re-escalation updates in place
    decision_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dead_letter (
    id            BIGSERIAL PRIMARY KEY,
    finding_hash  TEXT NOT NULL,
    error         TEXT NOT NULL,
    decision_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- LangGraph's PostgresSaver manages its own checkpoint tables via saver.setup();
-- see app/persistence/get_checkpointer().
