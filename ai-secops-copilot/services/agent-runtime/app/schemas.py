"""Pydantic schemas: the structured-output contract (ADR-010).

Every LLM response is validated against ``AnalysisResult`` before it is allowed
to drive any tool call. The ``Finding`` schema is the normalized SARIF/Semgrep
input contract (ADR-007) and matches the golden dataset records.

Requires pydantic v2 (a runtime dependency). Pure-logic modules (domain,
governance, idempotency) avoid this import so they stay testable without it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .domain import Action, Disposition, Severity


class Finding(BaseModel):
    """Normalized finding input (SARIF/Semgrep-style)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    scanner: str = "semgrep"
    ruleId: str
    title: str
    message: str
    file: str
    startLine: int | None = None
    endLine: int | None = None
    codeSnippet: str | None = None
    cwe: str | None = None
    owasp: str | None = None
    scannerSeverity: str | None = None


class AnalysisResult(BaseModel):
    """Validated output of the Finding Analysis Node.

    This is the schema the LLM must conform to; invalid output triggers a bounded
    re-prompt and then escalation (see PRODUCT_VISION.md failure handling).
    """

    model_config = ConfigDict(extra="forbid")

    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    recommendedAction: Action


class Citation(BaseModel):
    """A retrieved knowledge-base reference grounding the analysis (ADR-001)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    source: str
    url: str | None = None
    score: float | None = None


class TicketDecision(BaseModel):
    """Output of the Ticket Decision Node after the Governance Gate."""

    model_config = ConfigDict(extra="forbid")

    findingId: str
    findingHash: str
    analysis: AnalysisResult
    disposition: Disposition
    requiresHuman: bool
    governanceReason: str
    reasonCode: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    finding: Finding


class AnalyzeResponse(BaseModel):
    decision: TicketDecision
