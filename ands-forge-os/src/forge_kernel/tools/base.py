"""Tool port + registry.

A ``Tool`` does one thing against a run workspace ``root`` and returns a result dict. The
``ToolRegistry`` is bound to a root (the run's workspace directory) and writes are
**sandboxed** to it: a tool can never escape the workspace, so an agent cannot write
outside the run's output tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class ToolError(RuntimeError):
    """A tool failed or was asked to do something outside its sandbox."""


@runtime_checkable
class Tool(Protocol):
    name: str

    def invoke(self, root: Path, **kwargs: Any) -> dict:  # pragma: no cover - protocol
        ...


def safe_join(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root``, refusing paths that escape the sandbox."""
    root = root.resolve()
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise ToolError(f"path {relative!r} escapes the workspace sandbox")
    return target


class ToolRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def invoke(self, tool: str, **kwargs: Any) -> dict:
        impl = self._tools.get(tool)
        if impl is None:
            raise ToolError(f"unknown tool {tool!r}")
        self.root.mkdir(parents=True, exist_ok=True)
        return impl.invoke(self.root, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools)
