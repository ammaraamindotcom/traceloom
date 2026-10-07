"""Endpoints for fixed, transparent evaluation runs."""

from fastapi import APIRouter

from app.evaluation.dataset import EVALUATION_SCENARIOS
from app.schemas import EvaluationRunRequest, EvaluationRunResult, EvaluationScenario
from app.services.evaluation_service import run_evaluation


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/scenarios", response_model=list[EvaluationScenario])
def list_evaluation_scenarios() -> list[EvaluationScenario]:
    return EVALUATION_SCENARIOS


@router.post("/run", response_model=EvaluationRunResult)
def run_evaluation_endpoint(request: EvaluationRunRequest) -> EvaluationRunResult:
    return run_evaluation(include_ai=request.include_ai)
