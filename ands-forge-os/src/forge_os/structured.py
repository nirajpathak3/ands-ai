"""Structured-output parsing + validation (ADR-010, ported from ai-secops-copilot).

Real models do not always return clean JSON: they wrap it in prose or ```json fences. This
module extracts the first JSON object from a completion, then validates that every required
key is present and non-empty. The caller (the LLM agent) uses the result to drive a
**bounded reprompt** — and, if the model never complies, a graceful fallback — so an agent
never acts on unvalidated output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort extraction of a single JSON object from a model completion."""
    if not text:
        return None
    text = text.strip()
    # 1) Whole thing is JSON.
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # 2) Fenced ```json ... ``` block.
    m = _FENCE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
    # 3) First balanced { ... } span.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (Mapping, Sequence)):
        return len(value) == 0
    return False


def validate_required(obj: Mapping | None, required: Sequence[str]) -> list[str]:
    """Return the list of required keys that are missing or empty (empty list == valid)."""
    if obj is None:
        return list(required) or ["<object>"]
    return [key for key in required if _is_empty(obj.get(key))]
