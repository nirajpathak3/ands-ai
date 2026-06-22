"""Core domain enums shared across the agent runtime.

Pure stdlib (no third-party imports) so this module is importable and testable
without installing the full runtime. These values are the canonical vocabulary
used by the dataset labels, the eval harness, and the LangGraph nodes.
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(str, Enum):
    """Triage action the Ticket Decision Node recommends."""

    CREATE_TICKET = "create_ticket"
    SUPPRESS = "suppress"
    ESCALATE = "escalate"


class Disposition(str, Enum):
    """Governance outcome from the confidence gate.

    Mirrors the obs-agent AuthorityEvaluationService pattern
    (APPROVED / SUGGESTED / SUPPRESSED) adapted to this product's
    two-threshold, three-disposition model.
    """

    AUTO_EXECUTE = "auto_execute"      # confidence >= autoThreshold
    HUMAN_APPROVAL = "human_approval"  # suggestThreshold <= confidence < autoThreshold
    ESCALATE = "escalate"              # confidence < suggestThreshold
