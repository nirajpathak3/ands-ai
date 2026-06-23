"""Knowledge-base corpus loading (ADR-001 RAG knowledge layer).

A ``Document`` is one retrievable unit of security guidance (an OWASP category or
a CWE entry). The corpus is authored clean-room from public standards and lives in
``datasets/knowledge/security-kb-v1.json``. Pure stdlib so it loads with no third-
party packages and the retriever stays trivially testable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# repo root = .../ai-secops-copilot (corpus.py is app/rag/corpus.py)
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_KB_PATH = _REPO_ROOT / "datasets" / "knowledge" / "security-kb-v1.json"


@dataclass(frozen=True)
class Document:
    """One knowledge-base entry (OWASP category or CWE)."""

    id: str
    type: str            # "owasp" | "cwe"
    title: str
    text: str
    source: str
    url: str | None = None
    cwe: str | None = None
    owasp: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def searchable_text(self) -> str:
        """All lexically-indexed text for this document."""
        parts = [self.title, self.text, " ".join(self.tags)]
        if self.cwe:
            parts.append(self.cwe)
        if self.owasp:
            parts.append(self.owasp)
        return " ".join(parts)


def load_documents(path: Path | str | None = None) -> list[Document]:
    kb_path = Path(path) if path else DEFAULT_KB_PATH
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base not found: {kb_path}")
    raw = json.loads(kb_path.read_text(encoding="utf-8"))
    docs: list[Document] = []
    for d in raw.get("documents", []):
        docs.append(
            Document(
                id=d["id"],
                type=d.get("type", ""),
                title=d.get("title", ""),
                text=d.get("text", ""),
                source=d.get("source", ""),
                url=d.get("url"),
                cwe=(d.get("cwe") or None),
                owasp=(d.get("owasp") or None),
                tags=tuple(d.get("tags", []) or ()),
            )
        )
    return docs


@lru_cache(maxsize=4)
def load_documents_cached(path: str | None = None) -> tuple[Document, ...]:
    """Process-cached corpus load (the KB is static at runtime)."""
    return tuple(load_documents(path))
