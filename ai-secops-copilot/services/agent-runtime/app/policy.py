"""Policy-as-code & suppression rules (Day 19, ADR-021).

A declarative rule layer that lets a tenant codify deterministic overrides on top of the
confidence-based governance gate: "always suppress findings like Y", "always escalate
anything touching auth", "never auto-act in this path". Policy is evaluated *after* analysis
and *after* the governance disposition, so a rule is a transparent, audited override of the
model's recommendation — not a hidden mutation of it.

Design:
  * **Rules are data** (`PolicyRule`): match on severity / ruleId / cwe / path-glob / tenant,
    first-match-wins, each with a stable id + human reason for the audit trail.
  * **Actions**: ``suppress`` (auto-dismiss, no ticket), ``force_escalate`` (always a human),
    ``force_ticket`` (always open a ticket), ``annotate`` (label only, no disposition change).
  * **Engine** (`PolicyEngine`) is per-tenant, tracks per-rule hit counts (observability), and
    `apply()` rewrites the decision in place, stamping ``reasonCode = policy:<id>`` and a
    ``policyApplied`` marker so the override is visible everywhere the decision flows.

Pure stdlib (``fnmatch``) so it stays trivially testable and reusable from the pipeline,
the compiled graph, and the dry-run endpoint alike.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from fnmatch import fnmatch

logger = logging.getLogger("secops.policy")

VALID_ACTIONS = frozenset({"suppress", "force_escalate", "force_ticket", "annotate"})


@dataclass(frozen=True)
class PolicyRule:
    """One declarative rule. Empty match facets mean 'match anything' for that facet."""

    id: str
    action: str
    severity: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()      # matches finding ruleId OR cwe
    path_globs: tuple[str, ...] = ()    # matches finding file path (fnmatch)
    tenants: tuple[str, ...] = ()       # restrict to these tenants (empty = all)
    reason: str = ""
    enabled: bool = True

    @staticmethod
    def from_dict(data: dict) -> PolicyRule:
        action = str(data.get("action", "")).strip().lower()
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"invalid policy action {action!r}; valid: {sorted(VALID_ACTIONS)}"
            )
        rid = str(data.get("id") or "").strip()
        if not rid:
            raise ValueError("policy rule requires a non-empty 'id'")

        def _tuple(key: str) -> tuple[str, ...]:
            value = data.get(key) or []
            if isinstance(value, str):
                value = [value]
            return tuple(str(v).strip() for v in value if str(v).strip())

        return PolicyRule(
            id=rid,
            action=action,
            severity=tuple(s.lower() for s in _tuple("severity")),
            rule_ids=_tuple("ruleIds") or _tuple("rule_ids"),
            path_globs=_tuple("paths") or _tuple("path_globs"),
            tenants=_tuple("tenants"),
            reason=str(data.get("reason", "")),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "action": self.action, "severity": list(self.severity),
            "ruleIds": list(self.rule_ids), "paths": list(self.path_globs),
            "tenants": list(self.tenants), "reason": self.reason, "enabled": self.enabled,
        }


@dataclass
class PolicyMatch:
    ruleId: str
    action: str
    reason: str
    disposition: str | None = None
    recommendedAction: str | None = None

    def to_dict(self) -> dict:
        return {
            "ruleId": self.ruleId, "action": self.action, "reason": self.reason,
            "disposition": self.disposition, "recommendedAction": self.recommendedAction,
        }


def _matches(rule: PolicyRule, finding: dict, severity: str) -> bool:
    severity = (severity or "").lower()
    if rule.severity and severity not in rule.severity:
        return False
    if rule.rule_ids:
        candidates = {
            str(finding.get("ruleId", "")), str(finding.get("cwe", "")),
        }
        if not (candidates & set(rule.rule_ids)):
            return False
    if rule.path_globs:
        path = str(finding.get("file", ""))
        if not any(fnmatch(path, glob) for glob in rule.path_globs):
            return False
    return True


@dataclass
class PolicyEngine:
    """Per-tenant ordered rule set with hit counters (first-match-wins)."""

    rules: list[PolicyRule] = field(default_factory=list)
    _hits: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._hits = {r.id: 0 for r in self.rules}

    def replace(self, rules: list[PolicyRule]) -> None:
        self.rules = list(rules)
        self._hits = {r.id: 0 for r in self.rules}

    @property
    def enabled_rules(self) -> list[PolicyRule]:
        return [r for r in self.rules if r.enabled]

    def hits(self) -> dict[str, int]:
        return dict(self._hits)

    def match(self, finding: dict, severity: str) -> PolicyRule | None:
        """Return the first enabled rule matching the finding (no side effects)."""
        for rule in self.enabled_rules:
            if _matches(rule, finding, severity):
                return rule
        return None

    def apply(self, finding: dict, decision: dict) -> PolicyMatch | None:
        """Override the decision in place if a rule matches; returns the match or None."""
        analysis = decision.get("analysis") or {}
        severity = str(analysis.get("severity", ""))
        rule = self.match(finding, severity)
        if rule is None:
            return None
        self._hits[rule.id] = self._hits.get(rule.id, 0) + 1
        reason = rule.reason or f"policy rule '{rule.id}' ({rule.action})"

        match = PolicyMatch(ruleId=rule.id, action=rule.action, reason=reason)
        if rule.action == "suppress":
            analysis["recommendedAction"] = "suppress"
            decision["analysis"] = analysis
            decision["disposition"] = "auto_execute"
            decision["requiresHuman"] = False
            match.disposition, match.recommendedAction = "auto_execute", "suppress"
        elif rule.action == "force_escalate":
            decision["disposition"] = "escalate"
            decision["requiresHuman"] = True
            match.disposition = "escalate"
        elif rule.action == "force_ticket":
            analysis["recommendedAction"] = "create_ticket"
            decision["analysis"] = analysis
            decision["disposition"] = "auto_execute"
            decision["requiresHuman"] = False
            match.disposition, match.recommendedAction = "auto_execute", "create_ticket"
        # annotate: no disposition change.

        if rule.action != "annotate":
            decision["reasonCode"] = f"policy:{rule.id}"
            decision["governanceReason"] = reason
        decision["policyApplied"] = match.to_dict()
        return match


def parse_rules(raw: object) -> list[PolicyRule]:
    """Parse a list of rule dicts (or a JSON string) into ``PolicyRule`` objects."""
    if isinstance(raw, str):
        raw = json.loads(raw or "[]")
    if not isinstance(raw, list):
        raise ValueError("policy rules must be a JSON list of rule objects")
    return [PolicyRule.from_dict(item) for item in raw]


def load_rules(settings) -> list[PolicyRule]:  # noqa: ANN001 - Settings (avoid import cycle)
    """Load policy rules from inline JSON or a file path (offline default: none)."""
    inline = getattr(settings, "policy_rules_inline", "") or ""
    if inline.strip():
        try:
            return parse_rules(inline)
        except Exception as exc:  # noqa: BLE001 - bad config must not break boot
            logger.warning("ignoring invalid POLICY_RULES inline config: %s", exc)
            return []
    path = getattr(settings, "policy_rules_path", "") or ""
    if path.strip():
        from pathlib import Path

        p = Path(path)
        if p.exists():
            try:
                return parse_rules(p.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("ignoring invalid policy rules file %s: %s", path, exc)
    return []


def build_engine(settings, tenant_id: str) -> PolicyEngine:  # noqa: ANN001
    """Build a tenant-scoped engine (rules with no tenant filter apply to everyone)."""
    rules = [r for r in load_rules(settings) if not r.tenants or tenant_id in r.tenants]
    return PolicyEngine(rules)
