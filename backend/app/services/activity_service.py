"""Database operations for activities."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.schemas import ActivityCreate


def create_activity(db: Session, payload: ActivityCreate) -> Activity:
    activity = Activity(
        user_id=payload.user_id,
        event_type=payload.event_type,
        timestamp=payload.timestamp,
        metadata_=payload.metadata,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def create_activities(db: Session, payloads: list[ActivityCreate]) -> list[Activity]:
    """Store a complete activity sequence in one transaction."""
    activities = [
        Activity(
            user_id=payload.user_id,
            event_type=payload.event_type,
            timestamp=payload.timestamp,
            metadata_=payload.metadata,
        )
        for payload in payloads
    ]
    db.add_all(activities)
    db.commit()
    for activity in activities:
        db.refresh(activity)
    return activities


def list_recent_activities(
    db: Session, limit: int = 100, user_id: str | None = None
) -> list[Activity]:
    statement = select(Activity)
    if user_id is not None:
        statement = statement.where(Activity.user_id == user_id)
    statement = statement.order_by(Activity.timestamp.desc()).limit(limit)
    return list(db.scalars(statement))
