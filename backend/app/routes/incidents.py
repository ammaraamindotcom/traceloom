"""HTTP endpoint for deterministic incident investigation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import IncidentInvestigationResult
from app.services.activity_service import list_recent_activities
from app.services.incident_service import investigate_user_activities


router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/{user_id}", response_model=IncidentInvestigationResult)
def get_incident_investigation(
    user_id: str, db: Session = Depends(get_db)
) -> IncidentInvestigationResult:
    try:
        activities = list_recent_activities(db, limit=1000, user_id=user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to retrieve activities for incident investigation") from exc
    if not activities:
        raise HTTPException(status_code=404, detail="No activities found for this user")
    return investigate_user_activities(user_id, activities)
