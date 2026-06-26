"""Agents — the kernel's worker contract + cross-cutting reviewers.

The kernel defines only the *ports*: an ``Agent`` produces one artifact from the
blackboard + its skill pack, and the cross-cutting ``Reviewer`` (Critic + red-team)
scores every artifact before a gate. Concrete agents live in a program (``forge_os``)
and are bound by role through the ``AgentRegistry`` — so the kernel stays generic.
"""

from __future__ import annotations

from .base import Agent, AgentContext, AgentResult
from .registry import AgentRegistry
from .reviewer import Reviewer, ReviewResult

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "AgentRegistry",
    "Reviewer",
    "ReviewResult",
]
