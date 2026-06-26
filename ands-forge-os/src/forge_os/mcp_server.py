"""MCP server for ANDS Forge OS — drive the product-development lifecycle from any MCP
client (Cursor, VS Code, Antigravity, Claude Desktop) over stdio.

This is the *primary* integration from PRODUCT-VISION §9: the kernel is a headless engine;
environments are just clients. The thin FastMCP wrapper here registers the dependency-free
tool logic in ``mcp_tools.py`` as MCP tools, sharing the durable ``RunStore`` with the CLI
and REST API — so a run started from your IDE can be approved from the dashboard, and vice
versa, keyed by ``run_id``.

Run it:
    pip install -e ".[mcp,llm]"
    forge-mcp                       # stdio transport (what MCP clients launch)

Register in an MCP client (example ``mcp.json``):
    { "mcpServers": { "ands-forge-os": { "command": "forge-mcp" } } }

Stays offline-deterministic by default; set FORGE_MODE=live + a provider key (.env) to use
real models behind the AI Gateway.
"""

from __future__ import annotations

from forge_os import build_forge

from . import mcp_tools

_INSTALL_HINT = (
    "The MCP server needs the 'mcp' package. Install it with:  pip install -e \".[mcp]\""
)


def build_server():
    """Build the FastMCP server with one shared, durable Forge engine behind the tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(_INSTALL_HINT) from exc

    forge = build_forge()
    mcp = FastMCP("ands-forge-os")

    @mcp.tool()
    def forge_start_run(vision: str) -> dict:
        """Start a product-development run from a vision. Runs autonomously until it
        completes or pauses at the first human-approval gate."""
        return mcp_tools.start_run(forge, vision)

    @mcp.tool()
    def forge_status(run_id: str) -> dict:
        """Get a run's status: current stage, cost, artifact statuses, and pending gate."""
        return mcp_tools.status(forge, run_id)

    @mcp.tool()
    def forge_approve(run_id: str, feedback: str = "") -> dict:
        """Approve the pending HITL gate and resume the run to the next gate or completion."""
        return mcp_tools.approve(forge, run_id, feedback)

    @mcp.tool()
    def forge_reject(run_id: str, feedback: str = "") -> dict:
        """Reject the pending gate, reopening the stage with feedback (bounded re-iteration)."""
        return mcp_tools.reject(forge, run_id, feedback)

    @mcp.tool()
    def forge_get_artifact(run_id: str, key: str) -> dict:
        """Fetch one produced artifact's content, review scores, and on-disk path."""
        return mcp_tools.get_artifact(forge, run_id, key)

    @mcp.tool()
    def forge_list_runs() -> dict:
        """List all runs in the workspace with a one-line summary each."""
        return mcp_tools.list_runs(forge)

    @mcp.tool()
    def forge_audit(run_id: str) -> dict:
        """The append-only audit trail for a run (the 'why' behind every decision)."""
        return mcp_tools.audit(forge, run_id)

    @mcp.tool()
    def forge_blueprint() -> dict:
        """The compiled lifecycle program: stages, artifacts, owning roles, and gate modes."""
        return mcp_tools.blueprint(forge)

    return mcp


def main() -> None:
    """Console entry point (``forge-mcp``). Serves over stdio for MCP clients."""
    build_server().run()


if __name__ == "__main__":
    main()
