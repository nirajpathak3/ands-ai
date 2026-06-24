"""Real Jira ticket adapter (Jira Cloud REST v3).

Implements the ``TicketProvider`` contract against Jira Cloud:
  * Idempotent create (ADR-009): before creating, a JQL search looks for an issue
    already labeled with this finding's hash; if found, it is returned instead of
    opening a duplicate. This survives process restarts (the key lives in Jira),
    which an in-memory map cannot.
  * Structured create: project, summary, ADF description, issue type, and labels
    (``secops-managed``, ``finding-<hash>``, ``sev-<severity>``).

Clean-room: written against Atlassian's public REST v3 documentation only. The
HTTP client is injectable so the adapter is fully unit-testable with a mocked
transport — no live Jira or credentials required to run the tests.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from ..ticketing import Ticket

# Jira labels may not contain spaces; finding_hash is hex so it is label-safe.
_MANAGED_LABEL = "secops-managed"


class JiraError(RuntimeError):
    """Raised when the Jira API returns a non-success response."""


def _adf(text: str) -> dict:
    """Minimal Atlassian Document Format wrapper for a plain-text paragraph."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text or ""}]}
        ],
    }


class JiraTicketProvider:
    """Provider-agnostic ticket sink backed by Jira Cloud."""

    name = "jira"

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str,
        issue_type: str = "Task",
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        if not (base_url and email and api_token and project_key):
            raise ValueError("JiraTicketProvider requires base_url, email, api_token, project_key")
        self._project_key = project_key
        self._issue_type = issue_type
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(email, api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=timeout,
        )
        # Tickets created/seen this session (for the /tickets listing).
        self._seen: dict[str, Ticket] = {}

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _hash_label(finding_hash: str) -> str:
        return f"finding-{finding_hash}"

    def _find_issue_key(self, finding_hash: str) -> str | None:
        jql = (
            f'project = "{self._project_key}" AND labels = "{self._hash_label(finding_hash)}" '
            "ORDER BY created DESC"
        )
        resp = self._client.post(
            "/rest/api/3/search/jql",
            json={"jql": jql, "maxResults": 1, "fields": ["key"]},
        )
        if resp.status_code >= 300:
            raise JiraError(f"Jira search failed ({resp.status_code}): {resp.text}")
        issues = resp.json().get("issues") or []
        return issues[0]["key"] if issues else None

    # -- TicketProvider contract -------------------------------------------
    def create(self, decision: Mapping[str, object], *, via: str = "auto") -> tuple[Ticket, bool]:
        finding_hash = str(decision.get("findingHash", ""))
        analysis = decision.get("analysis") or {}
        severity = (
            str(analysis.get("severity", "unknown"))
            if isinstance(analysis, Mapping) else "unknown"
        )
        finding_id = decision.get("findingId")
        reason = str(analysis.get("reason", "")) if isinstance(analysis, Mapping) else ""

        # Idempotency: return the existing issue if one is already labeled with this hash.
        existing_key = self._find_issue_key(finding_hash)
        if existing_key is not None:
            ticket = Ticket(
                key=existing_key, findingId=str(finding_id) if finding_id is not None else None,
                findingHash=finding_hash, severity=severity,
                summary=f"[{severity.upper()}] {finding_id}: security finding requires remediation",
                createdVia=via, provider=self.name,
            )
            self._seen[finding_hash] = ticket
            return ticket, False

        summary = f"[{severity.upper()}] {finding_id}: security finding requires remediation"
        description = (
            f"Finding {finding_id} ({finding_hash}).\n\n"
            f"Severity: {severity}\nGovernance: {decision.get('disposition')}\n\n{reason}"
        )
        payload = {
            "fields": {
                "project": {"key": self._project_key},
                "summary": summary,
                "description": _adf(description),
                "issuetype": {"name": self._issue_type},
                "labels": [
                    _MANAGED_LABEL,
                    self._hash_label(finding_hash),
                    f"sev-{severity}",
                ],
            }
        }
        resp = self._client.post("/rest/api/3/issue", json=payload)
        if resp.status_code >= 300:
            raise JiraError(f"Jira create failed ({resp.status_code}): {resp.text}")

        key = resp.json().get("key")
        if not key:
            raise JiraError(f"Jira create returned no key: {resp.text}")

        ticket = Ticket(
            key=key, findingId=str(finding_id) if finding_id is not None else None,
            findingHash=finding_hash, severity=severity, summary=summary,
            createdVia=via, provider=self.name,
        )
        self._seen[finding_hash] = ticket
        return ticket, True

    def get(self, finding_hash: str) -> Ticket | None:
        return self._seen.get(finding_hash)

    def all(self) -> list[Ticket]:
        return list(self._seen.values())

    def transition(self, finding_hash: str, status: str) -> Ticket | None:
        """Reflect a lifecycle status locally (Day 16).

        A production transition would resolve the target Jira *transition id* (the
        workflow is project-specific) via ``GET /issue/{key}/transitions`` and
        ``POST`` it; the platform-side lifecycle/SLA tracking is driven from the
        cached ticket here so the remediation view works the same across providers.
        """
        ticket = self._seen.get(finding_hash)
        if ticket is None:
            return None
        ticket.apply_status(status)
        return ticket

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
