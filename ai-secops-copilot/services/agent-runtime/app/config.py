"""Runtime configuration.

Implemented with stdlib only (dataclass + os.environ) so it imports without any
third-party packages installed. As the service grows this can migrate to
pydantic-settings (already listed as a dependency) without changing call sites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .governance import DEFAULT_AUTO_THRESHOLD, DEFAULT_SUGGEST_THRESHOLD


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Service
    service_name: str = os.environ.get("SERVICE_NAME", "agent-runtime")
    environment: str = os.environ.get("ENVIRONMENT", "development")
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8088"))

    # AI Gateway (single LLM egress; the runtime never calls providers directly).
    gateway_base_url: str = os.environ.get("GATEWAY_BASE_URL", "http://localhost:3000")

    # Governance thresholds (overridable via env; defaults from PRODUCT_VISION.md).
    auto_threshold: float = _env_float("GOVERNANCE_AUTO_THRESHOLD", DEFAULT_AUTO_THRESHOLD)
    suggest_threshold: float = _env_float("GOVERNANCE_SUGGEST_THRESHOLD", DEFAULT_SUGGEST_THRESHOLD)

    # Bounded re-prompts when the model returns invalid structured output (ADR-010).
    analysis_max_retries: int = int(os.environ.get("ANALYSIS_MAX_RETRIES", "2"))

    # RAG knowledge layer (ADR-001): retrieve OWASP/CWE guidance to ground analysis.
    # Offline lexical retriever by default; pgvector (ADR-002) when DATABASE_URL is set.
    rag_enabled: bool = os.environ.get("RAG_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    rag_top_k: int = int(os.environ.get("RAG_TOP_K", "3"))

    # Ticketing (ADR-008): mock (default) | jira | servicenow.
    ticket_provider: str = os.environ.get("TICKET_PROVIDER", "mock")
    jira_base_url: str = os.environ.get("JIRA_BASE_URL", "")
    jira_email: str = os.environ.get("JIRA_EMAIL", "")
    jira_api_token: str = os.environ.get("JIRA_API_TOKEN", "")
    jira_project_key: str = os.environ.get("JIRA_PROJECT_KEY", "")
    jira_issue_type: str = os.environ.get("JIRA_ISSUE_TYPE", "Task")

    # Data stores (wired Day 5+; placeholders for now).
    database_url: str = os.environ.get("DATABASE_URL", "")
    redis_url: str = os.environ.get("REDIS_URL", "")


def get_settings() -> Settings:
    return Settings()
