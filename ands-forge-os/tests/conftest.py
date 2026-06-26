"""Pytest bootstrap: pin a hermetic, offline-deterministic environment.

This runs before any test module imports ``forge_kernel.config`` (whose Settings
field defaults are evaluated at import time), so the suite is never influenced by a
developer's local ``.env`` (e.g. one carrying a real GEMINI_API_KEY + FORGE_MODE=live).
"""
from __future__ import annotations

import os

# Disable .env auto-loading for tests by pinning an explicit non-file path.
os.environ["FORGE_ENV_FILE"] = os.devnull
os.environ["FORGE_MODE"] = "offline"
os.environ["FORGE_FAKE_LIVE"] = "false"
for _key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
    os.environ[_key] = ""
