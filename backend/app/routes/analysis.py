"""HTTP API for deterministic behavioral analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalysisResult
from app.services.activity_service import list_recent_activities
from app.services.analysis_service import analyze_user_activities


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{user_id}", response_model=AnalysisResult)
def get_analysis(user_id: str, db: Session = Depends(get_db)) -> AnalysisResult:
    try:
        activities = list_recent_activities(db, limit=1000, user_id=user_id)
        if not activities:
            raise HTTPException(status_code=404, detail="No activities found for this user")
        return analyze_user_activities(user_id, activities)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to analyze activities") from exc
