"""Tests for the RAG knowledge layer (corpus, retrieval, grounding, citations)."""

import pytest

from app.rag import LexicalRetriever, format_context, get_default_retriever
from app.rag.corpus import load_documents
from app.rag.pgvector import PgVectorRetriever


def test_corpus_loads_owasp_and_cwe():
    docs = load_documents()
    assert len(docs) >= 20
    types = {d.type for d in docs}
    assert {"owasp", "cwe"} <= types
    # Every CWE doc has a CWE id; OWASP docs an OWASP id.
    assert all(d.cwe for d in docs if d.type == "cwe")
    assert all(d.owasp for d in docs if d.type == "owasp")


def test_exact_cwe_id_is_ranked_first():
    r = get_default_retriever()
    hits = r.retrieve("anything at all", k=3, cwe="CWE-89")
    assert hits, "expected at least one hit"
    assert hits[0].document.cwe == "CWE-89"
    assert hits[0].document.id == "cwe-89"


def test_retrieve_for_finding_grounds_on_cwe():
    r = get_default_retriever()
    finding = {
        "cwe": "CWE-78",
        "owasp": "A03:2021",
        "ruleId": "dangerous-subprocess-use",
        "title": "Command injection",
        "message": "subprocess called with shell=True and user input",
    }
    hits = r.retrieve_for_finding(finding, k=3)
    assert hits[0].document.cwe == "CWE-78"
    # A citation is JSON-serializable and carries provenance.
    cite = hits[0].to_citation()
    assert cite["id"] == "cwe-78"
    assert cite["source"] and cite["title"]


def test_lexical_recall_without_cwe_id():
    r = get_default_retriever()
    # No CWE id at all -> must still retrieve via lexical terms.
    hits = r.retrieve("sql injection parameterized query database", k=3)
    ids = {h.document.id for h in hits}
    assert "cwe-89" in ids or "owasp-a03-2021" in ids


def test_format_context_is_citeable_and_empty_safe():
    r = get_default_retriever()
    hits = r.retrieve("", k=3, cwe="CWE-89")
    ctx = format_context(hits)
    assert "[cwe-89]" in ctx
    assert format_context([]) == ""


def test_unknown_query_returns_nothing():
    r = LexicalRetriever()
    assert r.retrieve("zzzzz nonexistentterm qqqq", k=3) == []


def test_pgvector_is_a_documented_seam():
    with pytest.raises(ValueError):
        PgVectorRetriever("")
    rv = PgVectorRetriever("postgresql://x")
    with pytest.raises(RuntimeError):
        rv.retrieve("x")


def test_pipeline_decision_carries_citations():
    from app.pipeline import run_pipeline
    from app.ticketing import ApprovalStore, EscalationQueue, MockTicketProvider

    finding = {
        "id": "F-RAG-1",
        "ruleId": "formatted-sql-query",
        "title": "SQLi",
        "message": "user input in SQL",
        "file": "app/api/users.py",
        "startLine": 42,
        "cwe": "CWE-89",
        "scannerSeverity": "ERROR",
        "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
    }
    out = run_pipeline(
        finding,
        provider=MockTicketProvider(),
        approvals=ApprovalStore(),
        escalations=EscalationQueue(),
    )
    citations = out["decision"]["citations"]
    assert citations, "expected RAG citations on the decision"
    assert citations[0]["id"] == "cwe-89"

