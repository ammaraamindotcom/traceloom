"""Routes for inserting deterministic activity simulations."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ActivityRead
from app.services.activity_service import create_activities
from app.services.simulator_service import SCENARIO_NAMES, generate_scenario


router = APIRouter(prefix="/simulate", tags=["simulator"])


@router.post("/{scenario_name}", response_model=list[ActivityRead], status_code=status.HTTP_201_CREATED)
def simulate_scenario(
    scenario_name: str,
    user_id: str = Query(default="simulated-user", min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> list[ActivityRead]:
    if scenario_name not in SCENARIO_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_name}")

    try:
        generated_activities = generate_scenario(scenario_name, user_id)
        return create_activities(db, generated_activities)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to store simulated activities") from exc
