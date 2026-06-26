"""Semantic cache for LLM completions (ported, ADR-014).

Cuts cost/latency by reusing a completion for a prompt identical or near-identical to one
seen before. Offline this uses a lexical approximation of semantic similarity — token-set
Jaccard over the normalized prompt — so it needs no embeddings and is deterministic in CI.
The production upgrade is cosine similarity over embeddings behind the same get/put seam.
"""

from __future__ import annotations

import re
from collections import OrderedDict

from .types import LLMResponse

_WORD = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def _tokens(normalized: str) -> frozenset[str]:
    return frozenset(normalized.split())


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


class SemanticCache:
    def __init__(self, *, similarity: float = 0.92, max_entries: int = 512) -> None:
        self.similarity = similarity
        self.max_entries = max_entries
        self._store: OrderedDict[str, tuple[frozenset[str], LLMResponse]] = OrderedDict()

    def get(self, prompt: str, *, fuzzy: bool = True) -> LLMResponse | None:
        norm = _normalize(prompt)
        exact = self._store.get(norm)
        if exact is not None:
            return exact[1]
        if not fuzzy:
            return None
        incoming = _tokens(norm)
        best_score = 0.0
        best: LLMResponse | None = None
        for tokens, response in self._store.values():
            score = _jaccard(incoming, tokens)
            if score > best_score:
                best_score, best = score, response
        return best if best_score >= self.similarity else None

    def put(self, prompt: str, response: LLMResponse) -> None:
        norm = _normalize(prompt)
        if norm in self._store:
            self._store.move_to_end(norm)
            return
        self._store[norm] = (_tokens(norm), response)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
