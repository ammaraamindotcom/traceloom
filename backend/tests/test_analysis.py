from datetime import datetime, timedelta, timezone
import uuid

from app.models.activity import Activity
from app.schemas import AnomalySignal
from app.services.analysis_service import analyze_user_activities
from app.services.anomaly_service import detect_anomaly_signals
from app.services.baseline_service import calculate_behavioral_baseline
from app.services.risk_service import calculate_risk_level, calculate_risk_score


BASE_TIME = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)


def activity(event_type, minute, metadata=None, user_id="user-1"):
    return Activity(
        id=uuid.uuid4(),
        user_id=user_id,
        event_type=event_type,
        timestamp=BASE_TIME + timedelta(minutes=minute),
        metadata_=metadata or {},
    )


def signal_types(activities, baseline):
    return {signal.type for signal in detect_anomaly_signals(activities, baseline)}


def test_calculates_behavioral_baseline_from_completed_sessions():
    activities = [
        activity("LOGIN", 0), activity("FILE_DOWNLOAD", 10, {"size_mb": 50}), activity("LOGOUT", 30),
        activity("LOGIN", 60), activity("REPOSITORY_ACCESS", 65), activity("DATABASE_QUERY", 70), activity("LOGOUT", 90),
    ]

    baseline = calculate_behavioral_baseline(activities)

    assert baseline.session_count == 2
    assert baseline.average_activities_per_session == 3.5
    assert baseline.average_file_downloads == 0.5
    assert baseline.average_repository_accesses == 0.5
    assert baseline.average_database_queries == 0.5
    assert baseline.average_session_duration_minutes == 30
    assert baseline.average_downloaded_data_mb == 25


def test_detects_high_download_volume():
    baseline = calculate_behavioral_baseline([activity("LOGIN", 0), activity("FILE_DOWNLOAD", 1), activity("LOGOUT", 2)])
    current = [activity("LOGIN", 10)] + [activity("FILE_DOWNLOAD", 11 + index) for index in range(5)]

    assert "HIGH_DOWNLOAD_VOLUME" in signal_types(current, baseline)


def test_detects_large_data_volume():
    baseline = calculate_behavioral_baseline([activity("LOGIN", 0), activity("FILE_DOWNLOAD", 1, {"size_mb": 20}), activity("LOGOUT", 2)])
    current = [activity("LOGIN", 10), activity("FILE_DOWNLOAD", 11, {"size_mb": 240})]

    assert "LARGE_DATA_VOLUME" in signal_types(current, baseline)


def test_detects_archive_after_downloads():
    baseline = calculate_behavioral_baseline([])
    current = [activity("FILE_DOWNLOAD", index, {"size_mb": 10}) for index in range(3)] + [activity("ARCHIVE_CREATED", 8)]

    assert "ARCHIVE_AFTER_DOWNLOADS" in signal_types(current, baseline)


def test_detects_external_upload_after_downloads():
    baseline = calculate_behavioral_baseline([])
    current = [activity("FILE_DOWNLOAD", index, {"size_mb": 10}) for index in range(3)] + [activity("EXTERNAL_UPLOAD", 8)]

    assert "EXTERNAL_UPLOAD_AFTER_DOWNLOADS" in signal_types(current, baseline)


def test_detects_unusual_event_sequence():
    baseline = calculate_behavioral_baseline([])
    current = [activity("FILE_DOWNLOAD", index) for index in range(3)] + [activity("ARCHIVE_CREATED", 5), activity("EXTERNAL_UPLOAD", 7)]

    assert "UNUSUAL_EVENT_SEQUENCE" in signal_types(current, baseline)


def test_risk_score_calculation():
    signals = [
        AnomalySignal(type="a", description="", severity="high", evidence={}),
        AnomalySignal(type="b", description="", severity="medium", evidence={}),
        AnomalySignal(type="c", description="", severity="low", evidence={}),
    ]

    assert calculate_risk_score(signals) == 6
    assert calculate_risk_level(2) == "low"
    assert calculate_risk_level(3) == "medium"
    assert calculate_risk_level(6) == "high"


def test_low_risk_analysis_for_repeated_normal_behavior():
    history = [activity("LOGIN", 0), activity("REPOSITORY_ACCESS", 1), activity("FILE_ACCESS", 2), activity("API_REQUEST", 3), activity("LOGOUT", 4)]
    current = [activity("LOGIN", 10), activity("REPOSITORY_ACCESS", 11), activity("FILE_ACCESS", 12), activity("API_REQUEST", 13), activity("LOGOUT", 14)]

    result = analyze_user_activities("user-1", history + current)

    assert result.risk_level == "low"
    assert result.signals == []


def test_medium_risk_analysis_for_unusual_download_volume():
    history = [activity("LOGIN", 0), activity("FILE_DOWNLOAD", 1), activity("LOGOUT", 2)]
    current = [activity("LOGIN", 10)] + [activity("FILE_DOWNLOAD", 11 + index) for index in range(5)]

    result = analyze_user_activities("user-1", history + current)

    assert result.risk_level == "medium"
    assert result.risk_score == 3


def test_high_risk_analysis_for_download_archive_upload_pattern():
    history = [activity("LOGIN", 0), activity("FILE_DOWNLOAD", 1, {"size_mb": 10}), activity("LOGOUT", 2)]
    current = [activity("LOGIN", 10)] + [activity("FILE_DOWNLOAD", 11 + index, {"size_mb": 200}) for index in range(5)] + [activity("ARCHIVE_CREATED", 20), activity("EXTERNAL_UPLOAD", 25)]

    result = analyze_user_activities("user-1", history + current)

    assert result.risk_level == "high"
    assert {signal.type for signal in result.signals} >= {"HIGH_DOWNLOAD_VOLUME", "ARCHIVE_AFTER_DOWNLOADS", "EXTERNAL_UPLOAD_AFTER_DOWNLOADS", "UNUSUAL_EVENT_SEQUENCE"}


def test_analysis_endpoint_returns_structured_result(client):
    client.post("/simulate/baseline-history?user_id=investigation-user")
    client.post("/simulate/possible-data-exfiltration?user_id=investigation-user")

    response = client.get("/analysis/investigation-user")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "investigation-user"
    assert body["risk_level"] == "high"
    assert body["baseline"]["session_count"] == 10
    assert "EXTERNAL_UPLOAD_AFTER_DOWNLOADS" in {signal["type"] for signal in body["signals"]}
