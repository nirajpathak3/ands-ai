"""Select a ticket provider from configuration (offline-safe default).

``TICKET_PROVIDER`` chooses the adapter:
  * ``mock``       (default) -> in-memory, no credentials, runs anywhere.
  * ``servicenow``           -> in-memory ServiceNow stand-in (still no creds).
  * ``jira``                 -> real Jira Cloud, requires JIRA_* settings.

If ``jira`` is requested but its credentials are incomplete, we log a warning and
fall back to the mock so the service still boots — credentials are added
just-in-time, not required up front.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..ticketing import MockTicketProvider, TicketProvider
from .jira import JiraTicketProvider
from .servicenow import ServiceNowTicketProvider

logger = logging.getLogger(__name__)


def get_ticket_provider(settings: Settings) -> TicketProvider:
    choice = (settings.ticket_provider or "mock").strip().lower()

    if choice == "jira":
        if settings.jira_base_url and settings.jira_email and \
                settings.jira_api_token and settings.jira_project_key:
            logger.info("Using Jira ticket provider (project %s).", settings.jira_project_key)
            return JiraTicketProvider(
                base_url=settings.jira_base_url,
                email=settings.jira_email,
                api_token=settings.jira_api_token,
                project_key=settings.jira_project_key,
                issue_type=settings.jira_issue_type,
            )
        logger.warning(
            "TICKET_PROVIDER=jira but JIRA_* settings are incomplete; falling back to mock."
        )
        return MockTicketProvider()

    if choice == "servicenow":
        logger.info("Using ServiceNow mock ticket provider.")
        return ServiceNowTicketProvider()

    return MockTicketProvider()
