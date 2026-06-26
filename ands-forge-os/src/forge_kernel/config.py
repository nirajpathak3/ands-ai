"""Kernel configuration (env-driven, safe offline defaults).

Stdlib only (dataclass + os.environ) so the kernel imports without any third-party
packages. The defaults make the kernel run **offline-deterministic**: deterministic
LLM provider (no keys, $0), in-memory run store, generous budget, and a default gate
mode that auto-passes when the eval bar is met. Flip env flags to go live.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ (real env vars always win)."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)  # don't override a real env var


def _load_dotenv() -> None:
    """Load a ``.env`` so keys live in one file. Real env vars take precedence.

    ``FORGE_ENV_FILE`` pins an explicit path (set it to a non-file to disable loading, as
    the test suite does for hermeticity). Otherwise the nearest ``.env`` from the current
    working directory upward is used.
    """
    explicit = os.environ.get("FORGE_ENV_FILE")
    if explicit is not None:
        path = Path(explicit)
        if path.is_file():
            _parse_env_file(path)
        return
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            _parse_env_file(candidate)
            return


_load_dotenv()  # must run before the Settings field defaults below are evaluated


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Gate materiality modes (the "materiality dial", PRODUCT_VISION §6).
GATE_ALWAYS_HUMAN = "always-human"
GATE_AUTO_IF_EVAL = "auto-if-eval"
GATE_AUTO = "auto"
GATE_MODES = (GATE_ALWAYS_HUMAN, GATE_AUTO_IF_EVAL, GATE_AUTO)


@dataclass(frozen=True)
class Settings:
    # Service / mode
    environment: str = os.environ.get("FORGE_ENV", "development")
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8099)
    # offline = deterministic stub agents + deterministic provider (no keys, $0).
    mode: str = os.environ.get("FORGE_MODE", "offline")

    # AI Gateway / LLM egress. No keys -> deterministic provider (reproducible, $0).
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    anthropic_base_url: str = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    # Gemini (Google AI Studio) — free-tier friendly, OpenAI-compatible REST surface.
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_base_url: str = os.environ.get(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
    )
    llm_timeout_s: float = _env_float("LLM_TIMEOUT_S", 30.0)
    llm_cache_enabled: bool = _env_bool("LLM_CACHE_ENABLED", True)
    llm_cache_similarity: float = _env_float("LLM_CACHE_SIMILARITY", 0.92)
    # Demo/test the live path with NO API keys: a scripted provider that behaves like a
    # real model (generates structured JSON, simulated cost). Only active in live mode.
    fake_live: bool = _env_bool("FORGE_FAKE_LIVE", False)
    fake_live_flaky: bool = _env_bool("FORGE_FAKE_LIVE_FLAKY", False)

    # Model tiers (assign which model does which task/stage; swap as new models ship).
    # A "strong" tier for reasoning-heavy work (judge/architecture) and a "cheap" tier for
    # high-volume drafting. Stages in ``strong_stages`` (or any artifact/stage ``model:``
    # override in the blueprint) use the strong tier even for the draft task.
    model_strong: str = os.environ.get("FORGE_MODEL_STRONG", "gemini-2.5-pro")
    model_cheap: str = os.environ.get("FORGE_MODEL_CHEAP", "gemini-2.5-flash")
    strong_stages: tuple[str, ...] = tuple(
        s.strip() for s in os.environ.get("FORGE_STRONG_STAGES", "technical").split(",")
        if s.strip()
    )

    # Scheduler + budget governor (PRODUCT_VISION §8). The governor can pause/escalate
    # a run that would exceed its cost or wall-clock budget.
    max_concurrency: int = _env_int("FORGE_MAX_CONCURRENCY", 4)
    budget_usd: float = _env_float("FORGE_BUDGET_USD", 5.0)
    budget_wall_seconds: float = _env_float("FORGE_BUDGET_WALL_SECONDS", 600.0)

    # Gates (materiality dial). Global default when a gate omits a mode.
    default_gate_mode: str = os.environ.get("FORGE_DEFAULT_GATE_MODE", GATE_AUTO_IF_EVAL)
    eval_quality_bar: float = _env_float("FORGE_EVAL_QUALITY_BAR", 0.75)
    # Bounded feedback-loop iterations on a rejected stage.
    max_stage_iterations: int = _env_int("FORGE_MAX_STAGE_ITERATIONS", 2)
    # Bounded reprompts when a live model returns invalid structured output (ADR-010).
    analysis_max_retries: int = _env_int("FORGE_ANALYSIS_MAX_RETRIES", 2)
    # LLM-as-judge for the Critic/Red-team review (live mode). Off -> the deterministic
    # heuristic Reviewer is the sole eval signal, which ~halves live LLM calls per run
    # (no judge call per artifact). Always a no-op offline regardless of this flag.
    llm_judge: bool = _env_bool("FORGE_LLM_JUDGE", True)

    # Workspace: where Forge writes run state + scaffolded product repos.
    workspace: str = os.environ.get("FORGE_WORKSPACE", "var")

    # Observability
    log_json: bool = _env_bool("LOG_JSON", False)
    otel_enabled: bool = _env_bool("OTEL_ENABLED", False)

    @property
    def offline(self) -> bool:
        return self.mode.strip().lower() != "live"


def get_settings() -> Settings:
    return Settings()
