-- Knowledge base schema for the RAG layer (ADR-001 / ADR-002).
-- Applied on top of init.sql (which enables the pgvector extension).
--
-- This is the production retrieval path used by PgVectorRetriever. The offline
-- default (LexicalRetriever) needs no database; this schema is provisioned when
-- DATABASE_URL is set and embeddings are wired (Day 5+ / Day 11 AI Gateway).
--
-- Embedding dimension 384 matches a small sentence-transformers model
-- (e.g. all-MiniLM-L6-v2); change the vector size if a different model is used.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id          TEXT PRIMARY KEY,           -- e.g. "cwe-89", "owasp-a03-2021"
    type        TEXT NOT NULL,              -- "cwe" | "owasp"
    cwe         TEXT,                       -- "CWE-89" when applicable
    owasp       TEXT,                       -- "A03:2021" when applicable
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    source      TEXT NOT NULL,
    url         TEXT,
    tags        TEXT[] DEFAULT '{}',
    embedding   vector(384),                -- populated at ingest time
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Exact-id lookups (the structured CWE/OWASP boost path).
CREATE INDEX IF NOT EXISTS idx_knowledge_cwe   ON knowledge_documents (cwe);
CREATE INDEX IF NOT EXISTS idx_knowledge_owasp ON knowledge_documents (owasp);

-- Approximate nearest-neighbour index for cosine similarity retrieval.
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
