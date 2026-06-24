"""Notifications & webhooks (Day 17, ADR-019).

Closing the loop with the humans and systems around the platform:

  * **Outbound** — when a finding is escalated, queued for approval, breaches its SLA, or
    is resolved, an event is dispatched to one or more channels. The ``log`` channel is
    always on (offline default); ``slack`` and a generic ``webhook`` channel activate only
    when their URL is configured, so dev/offline needs no external services. Delivery is
    best-effort and recorded per-notification (a channel outage never breaks the request).
  * **Inbound** — provider webhooks (Jira/ServiceNow) drive *real-time* lifecycle sync:
    a developer closing the ticket flows straight back into platform state. Requests are
    authenticated by an HMAC-SHA256 signature when ``WEBHOOK_SECRET`` is set.

Kept dependency-light (stdlib ``hmac``/``hashlib`` + the already-present ``httpx``) and
side-effect-isolated so it is easy to test and reason about.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import httpx

from .config import Settings

logger = logging.getLogger("secops.notify")

# Event taxonomy -> default severity (drives channel formatting + dashboard styling).
EVENT_SEVERITY = {
    "escalation": "warning",
    "approval_required": "info",
    "sla_breach": "critical",
    "ticket_resolved": "info",
}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def sign(secret: str, body: bytes) -> str:
    """HMAC-SHA256 hex digest of ``body`` (shared in/outbound webhook signing)."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Constant-time verify an inbound webhook signature.

    Open when no secret is configured (dev/offline); otherwise a valid
    ``sha256=<hex>`` (or bare hex) signature is required.
    """
    if not secret:
        return True
    if not signature:
        return False
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided[len("sha256="):]
    return hmac.compare_digest(sign(secret, body), provided)


@dataclass
class Notification:
    timestamp: str
    event: str
    severity: str
    title: str
    message: str
    findingHash: str | None = None
    findingId: str | None = None
    delivery: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Channel(Protocol):
    name: str

    def send(self, n: Notification) -> dict:
        ...


def _post_json(
    url: str, payload: dict, *, secret: str, timeout: float, client: httpx.Client | None
) -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Signature"] = "sha256=" + sign(secret, body)
    owns = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        resp = client.post(url, content=body, headers=headers)
        return {"ok": resp.status_code < 300, "status": resp.status_code}
    except Exception as exc:  # noqa: BLE001 - delivery failures are recorded, not raised
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if owns:
            client.close()


class LogChannel:
    """Always-on channel: structured log line (the offline default)."""

    name = "log"

    def send(self, n: Notification) -> dict:
        logger.info("notify event=%s severity=%s %s", n.event, n.severity, n.message)
        return {"channel": self.name, "ok": True}


class WebhookChannel:
    """Generic outbound webhook: POSTs the full notification JSON (optionally signed)."""

    name = "webhook"

    def __init__(
        self, url: str, *, secret: str = "", timeout: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._secret = secret
        self._timeout = timeout
        self._client = client

    def send(self, n: Notification) -> dict:
        res = _post_json(
            self._url, n.to_dict(), secret=self._secret,
            timeout=self._timeout, client=self._client,
        )
        return {"channel": self.name, **res}


class SlackChannel:
    """Slack incoming-webhook channel: posts a human-readable ``text`` payload."""

    name = "slack"

    def __init__(
        self, url: str, *, timeout: float = 5.0, client: httpx.Client | None = None
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._client = client

    def send(self, n: Notification) -> dict:
        text = f"[{n.severity.upper()}] {n.title} — {n.message}"
        res = _post_json(
            self._url, {"text": text}, secret="",
            timeout=self._timeout, client=self._client,
        )
        return {"channel": self.name, **res}


class NotificationCenter:
    """Per-tenant fan-out + recent-history buffer with per-finding dedupe."""

    def __init__(
        self, channels: list[Channel], *, enabled: bool = True, buffer: int = 200
    ) -> None:
        self._channels = list(channels)
        self._enabled = enabled
        self._buffer = buffer
        self._log: list[Notification] = []
        self._seen: set[tuple[str, str]] = set()  # (event, findingHash) dedupe

    @property
    def channels(self) -> list[str]:
        return [c.name for c in self._channels]

    def emit(
        self, event: str, *, title: str, message: str,
        finding_hash: str | None = None, finding_id: str | None = None,
        dedupe: bool = True,
    ) -> Notification | None:
        """Build, dispatch, and record one notification (None if disabled/deduped)."""
        if not self._enabled:
            return None
        if dedupe and finding_hash:
            key = (event, finding_hash)
            if key in self._seen:
                return None
            self._seen.add(key)

        n = Notification(
            timestamp=_now_iso(), event=event,
            severity=EVENT_SEVERITY.get(event, "info"),
            title=title, message=message,
            findingHash=finding_hash, findingId=finding_id,
        )
        for ch in self._channels:
            try:
                n.delivery.append(ch.send(n))
            except Exception as exc:  # noqa: BLE001 - never let a channel break the caller
                n.delivery.append(
                    {"channel": getattr(ch, "name", "?"), "ok": False, "error": str(exc)}
                )
        self._log.append(n)
        if len(self._log) > self._buffer:
            self._log = self._log[-self._buffer:]
        return n

    def list_recent(self, limit: int = 50) -> list[Notification]:
        return list(reversed(self._log[-limit:]))

    def clear(self) -> None:
        self._log.clear()
        self._seen.clear()


def build_channels(
    settings: Settings, *, client: httpx.Client | None = None
) -> list[Channel]:
    channels: list[Channel] = [LogChannel()]
    if settings.slack_webhook_url:
        channels.append(
            SlackChannel(
                settings.slack_webhook_url,
                timeout=settings.webhook_timeout_s, client=client,
            )
        )
    if settings.notify_webhook_url:
        channels.append(
            WebhookChannel(
                settings.notify_webhook_url, secret=settings.webhook_secret,
                timeout=settings.webhook_timeout_s, client=client,
            )
        )
    return channels


def build_notification_center(
    settings: Settings, *, client: httpx.Client | None = None
) -> NotificationCenter:
    return NotificationCenter(
        build_channels(settings, client=client),
        enabled=settings.notifications_enabled,
    )


# --- inbound webhook parsing (real-time lifecycle sync) ---------------------

# Provider status vocabulary -> our canonical lifecycle status.
_STATUS_ALIASES = {
    "open": "open", "new": "open", "to do": "open", "todo": "open", "reopened": "open",
    "in progress": "in_progress", "in_progress": "in_progress", "work in progress": "in_progress",
    "resolved": "resolved",
    "done": "done", "complete": "done", "completed": "done",
    "closed": "closed", "cancelled": "closed", "canceled": "closed",
}


def normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    return _STATUS_ALIASES.get(raw.strip().lower())


def _hash_from_labels(labels: Any) -> str | None:
    for label in labels or []:
        if isinstance(label, str) and label.startswith("finding-"):
            return label[len("finding-"):]
    return None


def parse_ticket_webhook(
    payload: Mapping[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Map a generic / Jira / ServiceNow webhook body to ``(finding_hash, status, tenant)``.

    * generic     -> ``{"findingHash": ..., "status": ..., "tenant": ...}``
    * Jira        -> ``{"issue": {"fields": {"labels": ["finding-<hash>"],
                        "status": {"name": "Done"}}}}``
    * ServiceNow  -> ``{"correlation_id": "<hash>", "state": "Resolved"}``
    """
    tenant = payload.get("tenant") or payload.get("tenantId")
    finding_hash = payload.get("findingHash")
    status = payload.get("status")

    issue = payload.get("issue")
    if finding_hash is None and isinstance(issue, Mapping):
        fields = issue.get("fields") or {}
        if isinstance(fields, Mapping):
            finding_hash = _hash_from_labels(fields.get("labels"))
            st = fields.get("status")
            if status is None and isinstance(st, Mapping):
                status = st.get("name")

    if finding_hash is None:
        finding_hash = payload.get("correlation_id")
        if status is None:
            status = payload.get("state")

    return (
        str(finding_hash) if finding_hash else None,
        normalize_status(str(status)) if status else None,
        str(tenant) if tenant else None,
    )
