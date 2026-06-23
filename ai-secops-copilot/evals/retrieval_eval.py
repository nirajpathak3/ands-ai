"""Retrieval-quality evaluation for the RAG layer (RAGAS-style context metrics).

Measures whether the knowledge retriever surfaces the *right* OWASP/CWE document for
each finding — the offline, deterministic analogue of RAGAS "context relevance".

For every golden finding that carries a CWE present in the knowledge base, the
relevant document is ``cwe-<n>``. We retrieve top-k for the finding and score:

  * hit@1     - relevant doc ranked first
  * hit@k     - relevant doc anywhere in top-k (== recall@k; 1 relevant doc each)
  * MRR       - mean reciprocal rank of the relevant doc
  * coverage  - fraction of CWE-bearing findings whose CWE exists in the KB

Coverage is reported separately and honestly: a finding whose CWE is not in the KB
is a *corpus gap*, not a retrieval miss, so it is excluded from hit/MRR (and flagged).

Uses the real ``LexicalRetriever`` so this measures the shipping retrieval path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AGENT_RUNTIME = _REPO_ROOT / "services" / "agent-runtime"
if str(_AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_AGENT_RUNTIME))


def _relevant_doc_id(cwe: str) -> str:
    """Map a finding CWE id to its knowledge-base document id ('CWE-89' -> 'cwe-89')."""
    return f"cwe-{cwe.strip().upper().removeprefix('CWE-').lower()}"


def evaluate_retrieval(dataset: dict, k: int = 3) -> Optional[dict]:
    """Compute retrieval metrics; returns None if the RAG layer is unavailable."""
    try:
        from app.rag.corpus import load_documents
        from app.rag.retriever import LexicalRetriever
    except Exception as exc:  # noqa: BLE001 - harness must degrade gracefully
        return {"available": False, "reason": f"RAG layer not importable: {exc}"}

    docs = load_documents()
    doc_ids = {d.id for d in docs}
    retriever = LexicalRetriever(docs)

    with_cwe = 0
    in_kb = 0
    hit1 = 0
    hitk = 0
    rr_sum = 0.0
    gaps: list[str] = []
    per_finding: list[dict] = []

    for finding in dataset.get("findings", []):
        cwe = str(finding.get("cwe") or "")
        if not cwe:
            continue
        with_cwe += 1
        relevant = _relevant_doc_id(cwe)
        if relevant not in doc_ids:
            gaps.append(cwe)
            per_finding.append({"id": finding.get("id"), "cwe": cwe, "inKB": False})
            continue

        in_kb += 1
        hits = retriever.retrieve_for_finding(finding, k=k)
        ranked_ids = [h.document.id for h in hits]
        rank = ranked_ids.index(relevant) + 1 if relevant in ranked_ids else 0
        if rank == 1:
            hit1 += 1
        if rank >= 1:
            hitk += 1
        rr_sum += (1.0 / rank) if rank >= 1 else 0.0
        per_finding.append({"id": finding.get("id"), "cwe": cwe, "inKB": True, "rank": rank})

    denom = in_kb or 1
    return {
        "available": True,
        "retriever": retriever.name,
        "k": k,
        "withCwe": with_cwe,
        "evaluated": in_kb,
        "coverage": in_kb / (with_cwe or 1),
        "hitRateAt1": hit1 / denom,
        "hitRateAtK": hitk / denom,
        "mrr": rr_sum / denom,
        "corpusGaps": sorted(set(gaps)),
        "perFinding": per_finding,
    }
