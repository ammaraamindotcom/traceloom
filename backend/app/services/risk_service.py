"""Small, explicit deterministic scoring rules for anomaly signals."""

from collections.abc import Iterable

from app.schemas import AnomalySignal


SEVERITY_POINTS = {"high": 3, "medium": 2, "low": 1}


def calculate_risk_score(signals: Iterable[AnomalySignal]) -> int:
    return sum(SEVERITY_POINTS[signal.severity] for signal in signals)


def calculate_risk_level(score: int) -> str:
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"
