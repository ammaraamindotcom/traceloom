"""Explicit ground truth and deterministic telemetry builders for evaluation."""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.activity import Activity
from app.schemas import EvaluationExpected, EvaluationScenario as EvaluationScenarioModel


def EvaluationScenario(
    scenario_id: str, name: str, description: str, expected: EvaluationExpected
) -> EvaluationScenarioModel:
    """Keep the fixed dataset compact while returning the typed schema model."""
    return EvaluationScenarioModel(
        scenario_id=scenario_id, name=name, description=description, expected=expected
    )


BASE_TIME = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)


def _activity(user_id: str, event_type: str, timestamp: datetime, metadata: dict | None = None) -> Activity:
    return Activity(id=uuid.uuid4(), user_id=user_id, event_type=event_type, timestamp=timestamp, metadata_=metadata or {})


def _baseline(user_id: str, include_password_change: bool = False) -> list[Activity]:
    activities: list[Activity] = []
    for day in range(5):
        start = BASE_TIME + timedelta(days=day)
        activities.extend([
            _activity(user_id, "LOGIN", start, {"method": "single-sign-on"}),
            _activity(user_id, "REPOSITORY_ACCESS", start + timedelta(minutes=4), {"repository": "internal-service", "action": "pull"}),
            _activity(user_id, "FILE_ACCESS", start + timedelta(minutes=15), {"filename": "guide.md"}),
            _activity(user_id, "API_REQUEST", start + timedelta(minutes=30), {"endpoint": "/v1/audit-events"}),
            _activity(user_id, "LOGOUT", start + timedelta(hours=7), {}),
        ])
        if include_password_change:
            activities.insert(-1, _activity(user_id, "PASSWORD_CHANGE", start + timedelta(hours=1), {"method": "self-service"}))
    return activities


def _current_start() -> datetime:
    return BASE_TIME + timedelta(days=7)


def _session(user_id: str, events: list[tuple[str, int, dict]]) -> list[Activity]:
    start = _current_start()
    return [_activity(user_id, event_type, start + timedelta(minutes=minutes), metadata) for event_type, minutes, metadata in events]


def _with_baseline(scenario_id: str, events: list[tuple[str, int, dict]], include_password_change: bool = False) -> list[Activity]:
    user_id = f"evaluation-{scenario_id}"
    return _baseline(user_id, include_password_change) + _session(user_id, events)


def _downloads(count: int, size_mb: int) -> list[tuple[str, int, dict]]:
    return [("FILE_DOWNLOAD", 5 + index * 2, {"filename": f"dataset-{index}.csv", "size_mb": size_mb, "source": "internal-drive"}) for index in range(count)]


EVALUATION_SCENARIOS = [
    EvaluationScenario("benign-developer-workday", "Normal developer workday", "Routine repository, file, and API activity.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-repository-browsing", "Normal repository browsing", "Routine repository access without bulk extraction.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-small-downloads", "Small legitimate downloads", "Two small files required for routine work.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-api-usage", "Normal API usage", "Routine audit API requests.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-login-logout", "Normal login and logout", "A short normal session.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-password-change", "Legitimate password change", "A normal self-service password rotation.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-moderate-files", "Moderate file activity", "Four small downloads below volume thresholds.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-archive-alone", "Archive without downloads", "An archive creation unrelated to bulk downloads.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-external-upload-alone", "External upload without bulk downloads", "A small standalone upload.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("benign-near-download-threshold", "Near download threshold", "Four small downloads remain below the deterministic count threshold.", EvaluationExpected(classification="BENIGN", risk_level="low", incident=False, signals=[], policy_decision="ALLOW")),
    EvaluationScenario("suspicious-high-downloads", "High-volume downloads", "Five downloads exceed the historical count baseline.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["HIGH_DOWNLOAD_VOLUME", "OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-large-data", "Large total data download", "Two very large files exceed the data-volume threshold.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["LARGE_DATA_VOLUME", "OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-archive-after-downloads", "Downloads followed by archive", "Three downloads are followed by archive creation.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["ARCHIVE_AFTER_DOWNLOADS", "OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-external-after-downloads", "Downloads followed by external upload", "Three downloads are followed by an external upload.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["EXTERNAL_UPLOAD_AFTER_DOWNLOADS", "OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-data-exfiltration", "Bulk download followed by external upload", "Bulk download, archive, and external-upload sequence.", EvaluationExpected(classification="SUSPICIOUS", risk_level="high", incident=True, signals=["HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME", "ARCHIVE_AFTER_DOWNLOADS", "EXTERNAL_UPLOAD_AFTER_DOWNLOADS", "UNUSUAL_EVENT_SEQUENCE", "OFF_PATTERN_ACTIVITY"], policy_decision="ESCALATE", intent="DATA_EXFILTRATION")),
    EvaluationScenario("suspicious-password-activity", "Unusual password activity", "Password activity that should receive additional review.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-repository-clone", "Bulk repository activity", "Repository cloning outside normal user behavior.", EvaluationExpected(classification="SUSPICIOUS", risk_level="medium", incident=False, signals=["OFF_PATTERN_ACTIVITY"], policy_decision="MONITOR")),
    EvaluationScenario("suspicious-multiple-behaviors", "Multiple suspicious behaviors", "Exfiltration pattern with an unusual password change.", EvaluationExpected(classification="SUSPICIOUS", risk_level="high", incident=True, signals=["HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME", "ARCHIVE_AFTER_DOWNLOADS", "EXTERNAL_UPLOAD_AFTER_DOWNLOADS", "UNUSUAL_EVENT_SEQUENCE", "OFF_PATTERN_ACTIVITY"], policy_decision="ESCALATE", intent="DATA_EXFILTRATION")),
    EvaluationScenario("suspicious-high-downloads-archive", "High downloads and archive", "Bulk extraction and archive creation without external upload.", EvaluationExpected(classification="SUSPICIOUS", risk_level="high", incident=True, signals=["HIGH_DOWNLOAD_VOLUME", "LARGE_DATA_VOLUME", "ARCHIVE_AFTER_DOWNLOADS", "OFF_PATTERN_ACTIVITY"], policy_decision="ESCALATE")),
    EvaluationScenario("suspicious-download-archive-upload", "Download archive upload sequence", "Smaller download sequence followed by archive and external upload.", EvaluationExpected(classification="SUSPICIOUS", risk_level="high", incident=True, signals=["ARCHIVE_AFTER_DOWNLOADS", "EXTERNAL_UPLOAD_AFTER_DOWNLOADS", "UNUSUAL_EVENT_SEQUENCE", "OFF_PATTERN_ACTIVITY"], policy_decision="ESCALATE", intent="DATA_EXFILTRATION")),
]


def build_scenario_activities(scenario_id: str) -> list[Activity]:
    normal = [("LOGIN", 0, {}), ("REPOSITORY_ACCESS", 4, {"repository": "internal-service", "action": "pull"}), ("FILE_ACCESS", 15, {"filename": "guide.md"}), ("API_REQUEST", 30, {"endpoint": "/v1/audit-events"}), ("LOGOUT", 60, {})]
    builders = {
        "benign-developer-workday": lambda: _with_baseline("benign-developer-workday", normal),
        "benign-repository-browsing": lambda: _with_baseline("benign-repository-browsing", [("LOGIN", 0, {}), ("REPOSITORY_ACCESS", 4, {"repository": "internal-service", "action": "browse"}), ("REPOSITORY_ACCESS", 15, {"repository": "platform", "action": "browse"}), ("LOGOUT", 45, {})]),
        "benign-small-downloads": lambda: _with_baseline("benign-small-downloads", [("LOGIN", 0, {}), *_downloads(2, 20), ("LOGOUT", 30, {})]),
        "benign-api-usage": lambda: _with_baseline("benign-api-usage", [("LOGIN", 0, {}), ("API_REQUEST", 5, {"endpoint": "/v1/audit-events"}), ("API_REQUEST", 10, {"endpoint": "/v1/audit-events"}), ("LOGOUT", 40, {})]),
        "benign-login-logout": lambda: _with_baseline("benign-login-logout", [("LOGIN", 0, {}), ("LOGOUT", 10, {})]),
        "benign-password-change": lambda: _with_baseline("benign-password-change", [("LOGIN", 0, {}), ("PASSWORD_CHANGE", 5, {"method": "self-service"}), ("LOGOUT", 15, {})], include_password_change=True),
        "benign-moderate-files": lambda: _with_baseline("benign-moderate-files", [("LOGIN", 0, {}), *_downloads(4, 20), ("LOGOUT", 40, {})]),
        "benign-archive-alone": lambda: _with_baseline("benign-archive-alone", [("LOGIN", 0, {}), ("ARCHIVE_CREATED", 15, {"filename": "project.zip"}), ("LOGOUT", 30, {})]),
        "benign-external-upload-alone": lambda: _with_baseline("benign-external-upload-alone", [("LOGIN", 0, {}), ("EXTERNAL_UPLOAD", 15, {"filename": "status.txt", "destination": "partner.example"}), ("LOGOUT", 30, {})]),
        "benign-near-download-threshold": lambda: _with_baseline("benign-near-download-threshold", [("LOGIN", 0, {}), *_downloads(4, 10), ("LOGOUT", 30, {})]),
        "suspicious-high-downloads": lambda: _with_baseline("suspicious-high-downloads", [("LOGIN", 0, {}), *_downloads(5, 10)]),
        "suspicious-large-data": lambda: _with_baseline("suspicious-large-data", [("LOGIN", 0, {}), *_downloads(2, 150)]),
        "suspicious-archive-after-downloads": lambda: _with_baseline("suspicious-archive-after-downloads", [("LOGIN", 0, {}), *_downloads(3, 10), ("ARCHIVE_CREATED", 15, {"filename": "dataset.zip"})]),
        "suspicious-external-after-downloads": lambda: _with_baseline("suspicious-external-after-downloads", [("LOGIN", 0, {}), *_downloads(3, 10), ("EXTERNAL_UPLOAD", 15, {"filename": "dataset.zip", "destination": "external.example"})]),
        "suspicious-data-exfiltration": lambda: _with_baseline("suspicious-data-exfiltration", [("LOGIN", 0, {}), *_downloads(5, 200), ("ARCHIVE_CREATED", 17, {"filename": "dataset.zip"}), ("EXTERNAL_UPLOAD", 25, {"filename": "dataset.zip", "destination": "external.example"})]),
        "suspicious-password-activity": lambda: _with_baseline("suspicious-password-activity", [("LOGIN", 0, {}), ("PASSWORD_CHANGE", 5, {"method": "self-service"}), ("LOGOUT", 15, {})]),
        "suspicious-repository-clone": lambda: _with_baseline("suspicious-repository-clone", [("LOGIN", 0, {}), ("REPOSITORY_CLONE", 5, {"repository": "internal-service"}), ("REPOSITORY_CLONE", 10, {"repository": "platform"}), ("LOGOUT", 30, {})]),
        "suspicious-multiple-behaviors": lambda: _with_baseline("suspicious-multiple-behaviors", [("LOGIN", 0, {}), *_downloads(5, 200), ("ARCHIVE_CREATED", 17, {"filename": "dataset.zip"}), ("EXTERNAL_UPLOAD", 25, {"filename": "dataset.zip", "destination": "external.example"}), ("PASSWORD_CHANGE", 35, {"method": "self-service"})]),
        "suspicious-high-downloads-archive": lambda: _with_baseline("suspicious-high-downloads-archive", [("LOGIN", 0, {}), *_downloads(5, 200), ("ARCHIVE_CREATED", 17, {"filename": "dataset.zip"})]),
        "suspicious-download-archive-upload": lambda: _with_baseline("suspicious-download-archive-upload", [("LOGIN", 0, {}), *_downloads(3, 10), ("ARCHIVE_CREATED", 15, {"filename": "dataset.zip"}), ("EXTERNAL_UPLOAD", 20, {"filename": "dataset.zip", "destination": "external.example"})]),
    }
    try:
        return builders[scenario_id]()
    except KeyError as exc:
        raise ValueError(f"Unknown evaluation scenario: {scenario_id}") from exc
