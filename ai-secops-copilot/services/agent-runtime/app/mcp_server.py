"""MCP server for the AI SecOps Copilot agent runtime — drive the governed pipeline from any
MCP client (Cursor, VS Code, Antigravity, Claude Desktop) over stdio.

A thin FastMCP wrapper around the dependency-free tool logic in ``mcp_tools.py``. Builds the
default tenant context + shared RAG retriever once, then exposes the copilot's core operations
as MCP tools. Offline-deterministic by default (no keys); set provider keys to use real models.

Run it:
    pip install -e ".[mcp,llm]"
    agent-runtime-mcp              # stdio transport (what MCP clients launch)

Register in an MCP client (example ``mcp.json``):
    { "mcpServers": { "secops-agent-runtime": { "command": "agent-runtime-mcp" } } }
"""

from __future__ import annotations

from . import mcp_tools
from .config import get_settings
from .rag import get_retriever
from .tenancy import TenantRegistry

_INSTALL_HINT = (
    "The MCP server needs the 'mcp' package. Install it with:  pip install -e \".[mcp]\""
)


def build_server():
    """Build the FastMCP server with a default-tenant context behind the tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(_INSTALL_HINT) from exc

    settings = get_settings()
    registry = TenantRegistry(settings)
    retriever = get_retriever(settings)

    def ctx():
        return registry.get(settings.default_tenant)

    mcp = FastMCP("secops-agent-runtime")

    @mcp.tool()
    def secops_analyze_finding(finding: dict) -> dict:
        """Run a normalized finding (id, ruleId, title, message, file) through the full
        governed pipeline: analysis → governance gate → action (ticket/approval/escalate)."""
        return mcp_tools.analyze_finding(ctx(), retriever, finding)

    @mcp.tool()
    def secops_governance_preview(confidence: float,
                                  recommended_action: str = "create_ticket") -> dict:
        """Preview the governance gate for a confidence score (no LLM):
        auto_execute / human_approval / escalate."""
        return mcp_tools.governance_preview(get_settings(), confidence, recommended_action)

    @mcp.tool()
    def secops_list_findings() -> dict:
        """Current-state findings (deduped), each with its linked ticket + pending-approval flag."""
        return mcp_tools.list_findings(ctx())

    @mcp.tool()
    def secops_list_approvals() -> dict:
        """Decisions awaiting human approval (the HITL queue)."""
        return mcp_tools.list_approvals(ctx())

    @mcp.tool()
    def secops_approve(finding_hash: str) -> dict:
        """Approve a queued decision → create the ticket (HITL gate)."""
        return mcp_tools.approve(ctx(), finding_hash)

    @mcp.tool()
    def secops_reject(finding_hash: str) -> dict:
        """Reject a queued decision (no ticket is created)."""
        return mcp_tools.reject(ctx(), finding_hash)

    @mcp.tool()
    def secops_audit() -> dict:
        """The append-only governance audit trail (the 'why' behind every decision)."""
        return mcp_tools.audit(ctx())

    @mcp.tool()
    def secops_metrics() -> dict:
        """Platform KPIs: automation rate, approvals, escalations, tickets, dead-letters."""
        return mcp_tools.metrics(ctx())

    @mcp.tool()
    def secops_knowledge_search(query: str, k: int = 3) -> dict:
        """Retrieve OWASP/CWE guidance for a free-text query (the RAG knowledge layer)."""
        return mcp_tools.knowledge_search(retriever, query, k)

    return mcp


def main() -> None:
    """Console entry point (``agent-runtime-mcp``). Serves over stdio for MCP clients."""
    build_server().run()


if __name__ == "__main__":
    main()
