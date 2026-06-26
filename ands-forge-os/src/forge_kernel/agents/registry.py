"""Bind artifact roles to concrete agent implementations.

The blueprint names a ``role`` per artifact; the registry resolves it to an ``Agent``.
A program registers its roster here. An optional ``default_factory`` lets a program back
every unmapped role with one generic stub agent (handy for the walking skeleton and for
auto-pass stub stages), so a blueprint can grow new artifacts without a code change.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import Agent


class AgentRegistry:
    def __init__(
        self, *, default_factory: Callable[[str], Agent] | None = None
    ) -> None:
        self._agents: dict[str, Agent] = {}
        self._default_factory = default_factory

    def register(self, agent: Agent) -> None:
        self._agents[agent.role] = agent

    def resolve(self, role: str) -> Agent:
        agent = self._agents.get(role)
        if agent is not None:
            return agent
        if self._default_factory is not None:
            agent = self._default_factory(role)
            self._agents[role] = agent
            return agent
        raise KeyError(f"no agent registered for role {role!r}")

    def roles(self) -> list[str]:
        return sorted(self._agents)
