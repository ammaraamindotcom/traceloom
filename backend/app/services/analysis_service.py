"""Orchestrates baseline calculation, signal detection, and scoring."""

from app.models.activity import Activity
from app.schemas import AnalysisResult
from app.services.anomaly_service import detect_anomaly_signals
from app.services.baseline_service import calculate_behavioral_baseline, group_activities_into_sessions
from app.services.risk_service import calculate_risk_level, calculate_risk_score


def analyze_user_activities(user_id: str, activities: list[Activity]) -> AnalysisResult:
    """Analyze the latest session against only earlier sessions when possible."""
    sessions = group_activities_into_sessions(activities)
    if not sessions:
        raise ValueError("Cannot analyze an empty activity history")

    recent_session = sessions[-1].activities
    historical_activities = [activity for session in sessions[:-1] for activity in session.activities]
    # A first observed session establishes an initial baseline but is not anomalous by itself.
    baseline = calculate_behavioral_baseline(historical_activities or recent_session)
    signals = detect_anomaly_signals(recent_session, baseline) if historical_activities else []
    risk_score = calculate_risk_score(signals)

    return AnalysisResult(
        user_id=user_id,
        risk_level=calculate_risk_level(risk_score),
        risk_score=risk_score,
        signals=signals,
        baseline=baseline,
        recent_activities=recent_session,
    )
