"""RAG knowledge layer: retrieve OWASP/CWE guidance to ground finding analysis.

Offline default is the pure-stdlib ``LexicalRetriever``; a ``PgVectorRetriever``
(ADR-002) slots in behind the same ``KnowledgeRetriever`` seam when DATABASE_URL is
configured. ``get_retriever`` selects the backend from settings.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from ..config import Settings
from .retriever import (
    KnowledgeRetriever,
    LexicalRetriever,
    Retrieved,
    format_context,
)

__all__ = [
    "KnowledgeRetriever",
    "LexicalRetriever",
    "Retrieved",
    "format_context",
    "get_retriever",
    "get_default_retriever",
]

logger = logging.getLogger(__name__)


def get_retriever(settings: Settings) -> KnowledgeRetriever | None:
    """Select a retriever from configuration (None when RAG is disabled)."""
    if not settings.rag_enabled:
        return None

    if settings.database_url:
        # pgvector is the production path; fall back to lexical until it is enabled.
        try:
            from .pgvector import PgVectorRetriever

            retriever = PgVectorRetriever(settings.database_url)
            _ = len(retriever)  # cheap availability probe
            logger.info("Using pgvector knowledge retriever.")
            return retriever
        except Exception as exc:  # noqa: BLE001 - any setup failure -> offline fallback
            logger.warning("pgvector retriever unavailable (%s); using lexical retriever.", exc)

    return get_default_retriever()


@lru_cache(maxsize=1)
def get_default_retriever() -> LexicalRetriever:
    """Process-cached offline retriever (the KB is static at runtime)."""
    return LexicalRetriever()
