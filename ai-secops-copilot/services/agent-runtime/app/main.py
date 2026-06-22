"""FastAPI entrypoint for the agent runtime.

Day-1 scaffold endpoints:
  * GET  /health             - liveness + config snapshot
  * POST /governance/preview - WORKS today: confidence -> disposition (no LLM)
  * POST /analyze            - full graph run (501 until Day 2 wires the LLM)

Run locally:
    uvicorn app.main:app --reload --port 8088
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .config import get_settings
from .domain import Action
from .governance import evaluate as governance_evaluate
from .schemas import AnalyzeRequest

app = FastAPI(
    title="AI Security Operations Copilot - Agent Runtime",
    version=__version__,
    summary="LangGraph agent runtime: Finding Analysis -> Ticket Decision -> Governance Gate.",
)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
        "governance": {
            "autoThreshold": settings.auto_threshold,
            "suggestThreshold": settings.suggest_threshold,
        },
    }


class GovernancePreviewRequest(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    recommendedAction: Action = Action.CREATE_TICKET


@app.post("/governance/preview")
def governance_preview(req: GovernancePreviewRequest) -> dict:
    """Demoable today: shows the two-threshold, three-disposition gate.

    e.g. confidence 0.95 -> auto_execute; 0.71 -> human_approval; 0.40 -> escalate.
    """
    settings = get_settings()
    decision = governance_evaluate(
        confidence=req.confidence,
        recommended_action=req.recommendedAction,
        auto_threshold=settings.auto_threshold,
        suggest_threshold=settings.suggest_threshold,
    )
    return {
        "confidence": req.confidence,
        "recommendedAction": req.recommendedAction.value,
        "disposition": decision.disposition.value,
        "requiresHuman": decision.requires_human,
        "reason": decision.reason,
    }


@app.post("/analyze")
def analyze(_req: AnalyzeRequest) -> dict:
    """Full graph run. Stubbed until Day 2 wires the Finding Analysis Node."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Not implemented yet. The walking skeleton (Finding -> LLM -> decision) "
            "is wired on Day 2. The /governance/preview endpoint works today."
        ),
    )
