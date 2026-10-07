"""Deterministic policy recommendations and explicitly safe dry-run simulations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DryRunInterventionRequest,
    DryRunInterventionResult,
    InterventionAuditRead,
    PolicyResult,
)
from app.services.activity_service import list_recent_activities
from app.services.analysis_service import analyze_user_activities
from app.services.intervention_service import list_intervention_audits, simulate_intervention
from app.services.policy_service import evaluate_policy


router = APIRouter(prefix="/policy", tags=["policy"])


def _policy_for_user(db: Session, user_id: str) -> PolicyResult:
    activities = list_recent_activities(db, limit=1000, user_id=user_id)
    if not activities:
        raise HTTPException(status_code=404, detail="No activities found for this user")
    return evaluate_policy(analyze_user_activities(user_id, activities))


@router.get("/{user_id}", response_model=PolicyResult)
def get_policy(user_id: str, db: Session = Depends(get_db)) -> PolicyResult:
    try:
        return _policy_for_user(db, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to evaluate deterministic policy") from exc


@router.post("/{user_id}/simulate", response_model=DryRunInterventionResult, status_code=201)
def simulate_policy_intervention(
    user_id: str,
    request: DryRunInterventionRequest,
    db: Session = Depends(get_db),
) -> DryRunInterventionResult:
    try:
        policy = _policy_for_user(db, user_id)
        recommendation = next(
            (item for item in policy.recommendations if item.action == request.action), None
        )
        if recommendation is None:
            raise HTTPException(status_code=400, detail="The requested action is not recommended for this user")
        return simulate_intervention(db, user_id, recommendation)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to record dry-run intervention") from exc


@router.get("/{user_id}/audit", response_model=list[InterventionAuditRead])
def get_policy_audit(user_id: str, db: Session = Depends(get_db)) -> list[InterventionAuditRead]:
    try:
        return list_intervention_audits(db, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to retrieve intervention audit history") from exc
