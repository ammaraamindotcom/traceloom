"""Endpoints for fixed, transparent evaluation runs."""

from fastapi import APIRouter, Request

from app.evaluation.dataset import EVALUATION_SCENARIOS
from app.schemas import EvaluationRunRequest, EvaluationRunResult, EvaluationScenario
from app.services.evaluation_service import run_evaluation
from app.services.rate_limit_service import limit_demo_writes, require_intent_access


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/scenarios", response_model=list[EvaluationScenario])
def list_evaluation_scenarios() -> list[EvaluationScenario]:
    return EVALUATION_SCENARIOS


@router.post("/run", response_model=EvaluationRunResult)
def run_evaluation_endpoint(request: EvaluationRunRequest, http_request: Request) -> EvaluationRunResult:
    limit_demo_writes(http_request)
    if request.include_ai:
        require_intent_access(http_request)
    return run_evaluation(include_ai=request.include_ai)
