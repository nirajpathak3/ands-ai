"""Runtime configuration.

Implemented with stdlib only (dataclass + os.environ) so it imports without any
third-party packages installed. As the service grows this can migrate to
pydantic-settings (already listed as a dependency) without changing call sites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .governance import (
    DEFAULT_AUTO_THRESHOLD,
    DEFAULT_SUGGEST_THRESHOLD,
    DEFAULT_SUPPRESS_AUTO_THRESHOLD,
)


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # Service
    service_name: str = os.environ.get("SERVICE_NAME", "agent-runtime")
    environment: str = os.environ.get("ENVIRONMENT", "development")
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8088"))

    # AI Gateway (single LLM egress; the runtime never calls providers directly).
    gateway_base_url: str = os.environ.get("GATEWAY_BASE_URL", "http://localhost:3000")

    # LLM egress (Day 11). The analysis node talks to one Gateway that routes across
    # providers with ordered fallback, a semantic cache, and cost/latency tracking.
    # Offline default: the deterministic provider (no keys) — fully reproducible. Real
    # providers activate only when their API key is present; deterministic is always the
    # final fallback so the runtime never hard-fails on a provider outage.
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    anthropic_base_url: str = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    llm_timeout_s: float = _env_float("LLM_TIMEOUT_S", 30.0)
    # Semantic cache: dedupe near-identical prompts to cut cost/latency (ADR-014).
    llm_cache_enabled: bool = os.environ.get("LLM_CACHE_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    llm_cache_similarity: float = _env_float("LLM_CACHE_SIMILARITY", 0.92)

    # Governance thresholds (overridable via env; defaults from PRODUCT_VISION.md).
    auto_threshold: float = _env_float("GOVERNANCE_AUTO_THRESHOLD", DEFAULT_AUTO_THRESHOLD)
    suggest_threshold: float = _env_float("GOVERNANCE_SUGGEST_THRESHOLD", DEFAULT_SUGGEST_THRESHOLD)
    # Stricter bar to auto-suppress than to auto-ticket (ADR-005, asymmetric risk).
    suppress_auto_threshold: float = _env_float(
        "GOVERNANCE_SUPPRESS_AUTO_THRESHOLD", DEFAULT_SUPPRESS_AUTO_THRESHOLD
    )

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

    # Observability (Day 12, ADR-015). In-process tracing + structured logs always on;
    # OTel export activates only when OTEL_ENABLED=true and the SDK is installed.
    otel_enabled: bool = os.environ.get("OTEL_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    otel_endpoint: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    log_json: bool = os.environ.get("LOG_JSON", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    # Alerting thresholds: a rule fires when the live rate/value exceeds these.
    alert_escalation_rate: float = _env_float("ALERT_ESCALATION_RATE", 0.30)
    alert_fallback_rate: float = _env_float("ALERT_FALLBACK_RATE", 0.20)
    alert_p95_latency_ms: float = _env_float("ALERT_P95_LATENCY_MS", 1500.0)
    alert_cost_per_request_usd: float = _env_float("ALERT_COST_PER_REQUEST_USD", 0.01)
    alert_approval_backlog: int = int(os.environ.get("ALERT_APPROVAL_BACKLOG", "25"))

    # Data stores. Persistence backend (Day 10) is derived from DATABASE_URL:
    #   ""/unset            -> in-memory (offline default)
    #   sqlite:///path.db   -> durable SQLite (local/CI durability)
    #   postgresql://...    -> Postgres (production; same SQL schema)
    database_url: str = os.environ.get("DATABASE_URL", "")
    redis_url: str = os.environ.get("REDIS_URL", "")

    # Multi-tenancy & API auth (Day 15, ADR-017). Off by default so the offline/dev
    # experience stays open (every request resolves to ``default_tenant``). When
    # AUTH_ENABLED=true the runtime requires an API key (``X-API-Key`` or
    # ``Authorization: Bearer``) or a signed JWT (HS256) carrying a ``tenant`` claim.
    auth_enabled: bool = _env_bool("AUTH_ENABLED", False)
    # API keys map a credential to a tenant: "key1:tenantA,key2:tenantB".
    api_keys_raw: str = os.environ.get("API_KEYS", "")
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    # When auth is disabled, a request may still pick a tenant via the X-Tenant-Id
    # header (so isolation is demoable offline); otherwise this default is used.
    default_tenant: str = os.environ.get("DEFAULT_TENANT", "public")
    # Per-tenant fixed-window rate limit (requests/minute). 0 disables limiting.
    rate_limit_rpm: int = int(os.environ.get("RATE_LIMIT_RPM", "0"))

    @property
    def api_keys(self) -> dict[str, str]:
        """Parse ``API_KEYS`` into a ``{api_key: tenant_id}`` mapping."""
        mapping: dict[str, str] = {}
        for pair in (self.api_keys_raw or "").split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            key, tenant = pair.split(":", 1)
            key, tenant = key.strip(), tenant.strip()
            if key and tenant:
                mapping[key] = tenant
        return mapping

    @property
    def persistence_backend(self) -> str:
        url = (self.database_url or "").strip().lower()
        if not url:
            return "memory"
        if url.startswith("sqlite"):
            return "sqlite"
        if url.startswith(("postgres://", "postgresql://")):
            return "postgres"
        return "memory"

    @property
    def sqlite_path(self) -> str:
        """Filesystem path from a sqlite URL (``sqlite:///x.db`` -> ``x.db``)."""
        url = (self.database_url or "").strip()
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        if url.startswith("sqlite://"):
            return url[len("sqlite://"):]
        return url


def get_settings() -> Settings:
    return Settings()
