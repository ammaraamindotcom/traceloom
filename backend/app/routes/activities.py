"""Activity ingestion and retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ActivityCreate, ActivityRead
from app.services.activity_service import create_activity, list_recent_activities
from app.services.rate_limit_service import limit_demo_writes


router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
def add_activity(
    payload: ActivityCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ActivityRead:
    limit_demo_writes(request)
    try:
        return create_activity(db, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to store activity") from exc


@router.get("", response_model=list[ActivityRead])
def get_activities(
    user_id: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> list[ActivityRead]:
    try:
        return list_recent_activities(db, user_id=user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to retrieve activities") from exc
