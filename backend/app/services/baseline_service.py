"""Calculation of explainable, historical user behavior baselines."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from app.models.activity import Activity
from app.schemas import BehavioralBaseline


@dataclass
class ActivitySession:
    activities: list[Activity]

    @property
    def started_at(self) -> datetime:
        return self.activities[0].timestamp

    @property
    def ended_at(self) -> datetime:
        return self.activities[-1].timestamp


def group_activities_into_sessions(activities: Iterable[Activity]) -> list[ActivitySession]:
    """Group chronological events using LOGIN/LOGOUT boundaries.

    Events before a LOGIN are retained as a fallback session so imported historical
    data is still analyzable.
    """
    sessions: list[ActivitySession] = []
    current: list[Activity] = []
    for activity in sorted(activities, key=lambda item: item.timestamp):
        if activity.event_type == "LOGIN" and current:
            sessions.append(ActivitySession(current))
            current = []
        current.append(activity)
        if activity.event_type == "LOGOUT":
            sessions.append(ActivitySession(current))
            current = []
    if current:
        sessions.append(ActivitySession(current))
    return sessions


def _download_size_mb(activity: Activity) -> float:
    value: Any = activity.metadata_.get("size_mb", 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def calculate_behavioral_baseline(activities: Iterable[Activity]) -> BehavioralBaseline:
    sessions = group_activities_into_sessions(activities)
    if not sessions:
        return BehavioralBaseline(
            session_count=0,
            average_activities_per_session=0,
            average_file_downloads=0,
            average_file_uploads=0,
            average_repository_accesses=0,
            average_database_queries=0,
            average_session_duration_minutes=0,
            average_downloaded_data_mb=0,
            most_common_event_types=[],
            event_type_counts={},
        )

    counts = Counter(activity.event_type for session in sessions for activity in session.activities)
    session_count = len(sessions)

    def average_for(event_types: set[str]) -> float:
        return round(
            sum(
                sum(activity.event_type in event_types for activity in session.activities)
                for session in sessions
            )
            / session_count,
            2,
        )

    durations = [
        max((session.ended_at - session.started_at).total_seconds() / 60, 0)
        for session in sessions
    ]
    downloaded_mb = [
        sum(_download_size_mb(activity) for activity in session.activities if activity.event_type == "FILE_DOWNLOAD")
        for session in sessions
    ]
    highest_count = max(counts.values())
    most_common = sorted(event_type for event_type, count in counts.items() if count == highest_count)

    return BehavioralBaseline(
        session_count=session_count,
        average_activities_per_session=round(sum(len(session.activities) for session in sessions) / session_count, 2),
        average_file_downloads=average_for({"FILE_DOWNLOAD"}),
        average_file_uploads=average_for({"FILE_UPLOAD"}),
        average_repository_accesses=average_for({"REPOSITORY_ACCESS", "REPOSITORY_CLONE"}),
        average_database_queries=average_for({"DATABASE_QUERY"}),
        average_session_duration_minutes=round(sum(durations) / session_count, 2),
        average_downloaded_data_mb=round(sum(downloaded_mb) / session_count, 2),
        most_common_event_types=most_common,
        event_type_counts=dict(sorted(counts.items())),
    )
