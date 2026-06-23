"""Knowledge retrieval for the RAG layer (ADR-001 / ADR-002).

The Finding Analysis Node retrieves OWASP/CWE guidance to ground its reasoning and
to cite *why* a finding is (or is not) a real risk. Retrieval sits behind a
``KnowledgeRetriever`` protocol so the offline default (a pure-stdlib lexical
retriever) and a future ``PgVectorRetriever`` (embeddings in Postgres, ADR-002) are
interchangeable — nothing downstream changes when the backend is swapped.

``LexicalRetriever`` is a small, dependency-free TF-IDF ranker with an exact-id
boost for CWE/OWASP identifiers, which is what makes structured findings resolve to
the right document deterministically (and keeps CI offline + reproducible).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .corpus import Document, load_documents_cached

Finding = Mapping[str, object]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Exact-identifier boosts dominate lexical score so a known CWE/OWASP id resolves
# to its own document first.
_CWE_BOOST = 100.0
_OWASP_BOOST = 40.0


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


@dataclass(frozen=True)
class Retrieved:
    """A retrieved document with its relevance score."""

    document: Document
    score: float

    def to_citation(self) -> dict:
        return {
            "id": self.document.id,
            "title": self.document.title,
            "source": self.document.source,
            "url": self.document.url,
            "score": round(self.score, 4),
        }


class KnowledgeRetriever(Protocol):
    """Provider-agnostic retrieval seam (lexical today, pgvector later)."""

    name: str

    def retrieve(self, query: str, *, k: int = 3) -> list[Retrieved]:
        ...

    def retrieve_for_finding(self, finding: Finding, *, k: int = 3) -> list[Retrieved]:
        ...

    def __len__(self) -> int:
        ...


class LexicalRetriever:
    """Offline TF-IDF retriever with exact CWE/OWASP id boosting (stdlib only)."""

    name = "lexical"

    def __init__(self, documents: list[Document] | tuple[Document, ...] | None = None) -> None:
        self._docs: tuple[Document, ...] = (
            tuple(documents) if documents is not None else load_documents_cached()
        )
        self._doc_tf: list[Counter[str]] = []
        df: Counter[str] = Counter()
        for doc in self._docs:
            tf = Counter(_tokenize(doc.searchable_text))
            self._doc_tf.append(tf)
            df.update(tf.keys())
        n = max(len(self._docs), 1)
        # Smoothed idf so common terms still contribute a little.
        self._idf: dict[str, float] = {
            term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()
        }

    def __len__(self) -> int:
        return len(self._docs)

    def _score(self, query_tokens: list[str], idx: int) -> float:
        tf = self._doc_tf[idx]
        if not tf:
            return 0.0
        score = 0.0
        for term in query_tokens:
            tf_t = tf.get(term)
            if tf_t:
                score += (1.0 + math.log(tf_t)) * self._idf.get(term, 0.0)
        return score

    def retrieve(
        self,
        query: str,
        *,
        k: int = 3,
        cwe: str | None = None,
        owasp: str | None = None,
    ) -> list[Retrieved]:
        query_tokens = _tokenize(query)
        cwe_norm = (cwe or "").upper() or None
        owasp_norm = (owasp or "").upper() or None

        scored: list[Retrieved] = []
        for idx, doc in enumerate(self._docs):
            score = self._score(query_tokens, idx)
            if cwe_norm and doc.cwe and doc.cwe.upper() == cwe_norm:
                score += _CWE_BOOST
            if owasp_norm and doc.owasp and doc.owasp.upper() == owasp_norm:
                score += _OWASP_BOOST
            if score > 0.0:
                scored.append(Retrieved(document=doc, score=score))

        scored.sort(key=lambda r: (-r.score, r.document.id))
        return scored[:k]

    def retrieve_for_finding(self, finding: Finding, *, k: int = 3) -> list[Retrieved]:
        """Build a query from a finding's structured + textual fields and retrieve.

        CWE/OWASP ids are passed for exact-match boosting; the free-text query adds
        lexical recall (e.g. an unknown CWE still matches via rule/title/message).
        """
        cwe = str(finding.get("cwe") or "")
        owasp = str(finding.get("owasp") or "")
        query = " ".join(
            str(finding.get(field) or "")
            for field in ("cwe", "owasp", "ruleId", "title", "message")
        )
        return self.retrieve(query, k=k, cwe=cwe, owasp=owasp)


def format_context(hits: list[Retrieved]) -> str:
    """Render retrieved docs as a compact, citeable knowledge block for the prompt."""
    if not hits:
        return ""
    lines = []
    for h in hits:
        d = h.document
        lines.append(f"[{d.id}] {d.title} (source: {d.source})\n{d.text}")
    return "\n\n".join(lines)
