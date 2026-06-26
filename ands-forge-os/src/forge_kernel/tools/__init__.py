"""Tools — the kernel's "syscalls": everything an agent can *do*, behind a port.

Each tool is invoked against a run workspace root and returns a small result dict (incl.
the relative path it wrote). The registry is the seam agents use, so adding a capability
(diagram, web_search, run_eval, ...) never touches the scheduler or agents' contracts.
"""

from __future__ import annotations

from .base import Tool, ToolError, ToolRegistry
from .filesystem import ScaffoldRepoTool, WriteFileTool
from .mockup import RenderMockupTool

__all__ = [
    "Tool",
    "ToolError",
    "ToolRegistry",
    "WriteFileTool",
    "ScaffoldRepoTool",
    "RenderMockupTool",
    "default_tools",
]


def default_tools(root) -> ToolRegistry:
    """The built-in tool set bound to a run workspace ``root``."""
    registry = ToolRegistry(root)
    registry.register(WriteFileTool())
    registry.register(ScaffoldRepoTool())
    registry.register(RenderMockupTool())
    return registry
