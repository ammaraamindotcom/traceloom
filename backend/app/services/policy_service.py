"""Inspectable, deterministic security-policy recommendations."""

from app.schemas import AnalysisResult, PolicyRecommendation, PolicyResult, PolicyRisk


DECISION_PRECEDENCE = {"ALLOW": 0, "MONITOR": 1, "CHALLENGE": 2, "RESTRICT": 3, "ESCALATE": 4}
ACTION_DECISIONS = {
    "ALLOW": "ALLOW",
    "MONITOR": "MONITOR",
    "REQUIRE_REAUTHENTICATION": "CHALLENGE",
    "REQUIRE_MFA": "CHALLENGE",
    "RESTRICT_EXTERNAL_UPLOAD": "RESTRICT",
    "TEMPORARILY_RESTRICT_DOWNLOADS": "RESTRICT",
    "ESCALATE_TO_SECURITY": "ESCALATE",
}


def _recommend(action: str, severity: str, reason: str, triggered_by: list[str]) -> PolicyRecommendation:
    return PolicyRecommendation(action=action, severity=severity, reason=reason, triggered_by=triggered_by)


def _overall_decision(recommendations: list[PolicyRecommendation]) -> tuple[str, str]:
    decision = max(
        (ACTION_DECISIONS[recommendation.action] for recommendation in recommendations),
        key=lambda item: DECISION_PRECEDENCE[item],
    )
    severity = {"ALLOW": "low", "MONITOR": "medium", "CHALLENGE": "medium", "RESTRICT": "high", "ESCALATE": "high"}[decision]
    return decision, severity


def evaluate_policy(analysis: AnalysisResult) -> PolicyResult:
    """Return recommendations using deterministic risk and signal combinations only."""
    signals_by_type = {signal.type: signal for signal in analysis.signals}
    signal_types = set(signals_by_type)
    recommendations: list[PolicyRecommendation] = []

    if analysis.risk_level == "low":
        recommendations.append(_recommend("ALLOW", "low", "No elevated deterministic risk was detected.", []))
    elif analysis.risk_level == "medium":
        recommendations.append(_recommend("MONITOR", "medium", "Deterministic activity signals warrant additional observation.", sorted(signal_types)))
    else:
        if "HIGH_DOWNLOAD_VOLUME" in signal_types:
            recommendations.append(_recommend("MONITOR", "medium", "Download volume exceeded the user's historical baseline.", ["HIGH_DOWNLOAD_VOLUME"]))
        if {"HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME"} <= signal_types:
            recommendations.append(_recommend("TEMPORARILY_RESTRICT_DOWNLOADS", "high", "High download count and cumulative data volume exceeded deterministic thresholds.", ["HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME"]))
        if "EXTERNAL_UPLOAD_AFTER_DOWNLOADS" in signal_types:
            triggers = [item for item in ["HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME", "EXTERNAL_UPLOAD_AFTER_DOWNLOADS"] if item in signal_types]
            recommendations.append(_recommend("RESTRICT_EXTERNAL_UPLOAD", "high", "An external upload followed a significant download sequence.", triggers))
        if "UNUSUAL_EVENT_SEQUENCE" in signal_types:
            recommendations.append(_recommend("REQUIRE_REAUTHENTICATION", "medium", "The download, archive, and external-upload sequence requires additional user verification.", ["UNUSUAL_EVENT_SEQUENCE"]))
        off_pattern = signals_by_type.get("OFF_PATTERN_ACTIVITY")
        if off_pattern and "PASSWORD_CHANGE" in off_pattern.evidence.get("absent_from_baseline", []):
            recommendations.append(_recommend("REQUIRE_MFA", "medium", "An unusual password-change event appeared outside the user's historical pattern.", ["OFF_PATTERN_ACTIVITY"]))
        high_signals = [signal.type for signal in analysis.signals if signal.severity == "high"]
        if len(high_signals) >= 2:
            recommendations.append(_recommend("ESCALATE_TO_SECURITY", "high", "Multiple high-severity deterministic signals require analyst investigation.", high_signals))
        if not recommendations:
            recommendations.append(_recommend("MONITOR", "medium", "High deterministic risk requires additional observation.", sorted(signal_types)))

    decision, decision_severity = _overall_decision(recommendations)
    return PolicyResult(
        user_id=analysis.user_id,
        risk=PolicyRisk(level=analysis.risk_level, score=analysis.risk_score),
        decision=decision,
        decision_severity=decision_severity,
        recommendations=recommendations,
        signals=analysis.signals,
        deterministic_analysis=analysis,
    )
