-- Initializes the Postgres database for the AI Security Operations Copilot.
-- Enables pgvector (ADR-002): one datastore for relational + vector data.
-- Schema/tables are created by the agent-runtime migrations on Day 5+.

CREATE EXTENSION IF NOT EXISTS vector;
