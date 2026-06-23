"""pgvector-backed retriever seam (ADR-002) — wired when DATABASE_URL is set.

The offline default is ``LexicalRetriever``. This class is the production retrieval
path: embed each knowledge document, store vectors in Postgres + pgvector, and rank
by cosine distance. It implements the same ``KnowledgeRetriever`` contract so the
node, pipeline, and API are unchanged when it is enabled.

It is intentionally a thin, documented stub today: enabling it requires the ``data``
extra (psycopg + pgvector) and an embeddings source via the AI Gateway (Day 11). The
SQL schema lives in ``infra/postgres/knowledge.sql``.
"""

from __future__ import annotations

from collections.abc import Mapping

from .retriever import Retrieved

Finding = Mapping[str, object]


class PgVectorRetriever:
    """Embeddings-backed retriever over Postgres + pgvector (enabled later)."""

    name = "pgvector"

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("PgVectorRetriever requires a DATABASE_URL")
        self._database_url = database_url

    def _unavailable(self) -> RuntimeError:
        return RuntimeError(
            "PgVectorRetriever is the Day 5+ production path and needs the 'data' extra "
            "(psycopg + pgvector) plus an embeddings source via the AI Gateway. Until then "
            "the runtime uses the offline LexicalRetriever. Schema: infra/postgres/knowledge.sql."
        )

    def __len__(self) -> int:
        return 0

    def retrieve(self, query: str, *, k: int = 3) -> list[Retrieved]:
        raise self._unavailable()

    def retrieve_for_finding(self, finding: Finding, *, k: int = 3) -> list[Retrieved]:
        raise self._unavailable()
