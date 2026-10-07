"""Dry-run intervention simulation and audit persistence; no external actions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intervention_audit import InterventionAudit
from app.schemas import DryRunInterventionResult, PolicyRecommendation


DRY_RUN_EFFECTS = {
    "ALLOW": "No action would be taken.",
    "MONITOR": "The user's future activity would be flagged for additional analyst review.",
    "REQUIRE_REAUTHENTICATION": "The user would be prompted to sign in again before continuing.",
    "REQUIRE_MFA": "The user would be prompted for an additional authentication factor.",
    "RESTRICT_EXTERNAL_UPLOAD": "Future external upload attempts would be denied pending analyst review.",
    "TEMPORARILY_RESTRICT_DOWNLOADS": "Future download attempts would be denied pending analyst review.",
    "ESCALATE_TO_SECURITY": "A security analyst case would be created for review.",
}


def simulate_intervention(
    db: Session, user_id: str, recommendation: PolicyRecommendation
) -> DryRunInterventionResult:
    audit = InterventionAudit(
        user_id=user_id,
        action=recommendation.action,
        severity=recommendation.severity,
        reason=recommendation.reason,
        triggered_by=recommendation.triggered_by,
        mode="DRY_RUN",
        executed=False,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return DryRunInterventionResult(
        audit_id=audit.id,
        mode="DRY_RUN",
        executed=False,
        action=recommendation.action,
        effect=DRY_RUN_EFFECTS[recommendation.action],
        reason=recommendation.reason,
        triggered_by=recommendation.triggered_by,
        affected_user=user_id,
        created_at=audit.created_at,
    )


def list_intervention_audits(db: Session, user_id: str) -> list[InterventionAudit]:
    statement = (
        select(InterventionAudit)
        .where(InterventionAudit.user_id == user_id)
        .order_by(InterventionAudit.created_at.desc())
    )
    return list(db.scalars(statement))
