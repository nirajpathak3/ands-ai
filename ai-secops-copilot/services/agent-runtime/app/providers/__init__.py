"""Ticket provider adapters (ADR-008): mock, real Jira, ServiceNow mock.

All adapters implement the ``TicketProvider`` protocol from ``app.ticketing`` and
are idempotent on ``findingHash`` (ADR-009). The orchestration/pipeline code is
provider-agnostic; ``get_ticket_provider`` selects one from configuration.
"""

from __future__ import annotations

from .factory import get_ticket_provider
from .jira import JiraError, JiraTicketProvider
from .servicenow import ServiceNowTicketProvider

__all__ = [
    "get_ticket_provider",
    "JiraTicketProvider",
    "JiraError",
    "ServiceNowTicketProvider",
]
