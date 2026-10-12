"""Explicit HTTP entry point for one LLM-backed intent inference."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import IntentAnalysisResult
from app.services.activity_service import list_recent_activities
from app.services.analysis_service import analyze_user_activities
from app.services.intent_service import IntentServiceError, infer_intent
from app.services.rate_limit_service import require_intent_access


router = APIRouter(prefix="/intent", tags=["intent"])


@router.get("/{user_id}", response_model=IntentAnalysisResult)
def get_intent_analysis(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_intent_access),
) -> IntentAnalysisResult:
    try:
        activities = list_recent_activities(db, limit=1000, user_id=user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to retrieve activities for intent analysis") from exc

    if not activities:
        raise HTTPException(status_code=404, detail="No activities found for this user")

    deterministic_analysis = analyze_user_activities(user_id, activities)
    try:
        intent_inference = infer_intent(deterministic_analysis)
    except IntentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return IntentAnalysisResult(
        deterministic_analysis=deterministic_analysis,
        intent_inference=intent_inference,
    )
