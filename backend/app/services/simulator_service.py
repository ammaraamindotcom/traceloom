"""Deterministic, realistic activity sequences for local development."""

from datetime import datetime, timedelta, timezone

from app.schemas import ActivityCreate


SCENARIO_NAMES = (
    "normal-workday",
    "baseline-history",
    "large-data-access",
    "possible-data-exfiltration",
    "credential-change",
)


def _event(
    user_id: str,
    event_type: str,
    timestamp: datetime,
    metadata: dict,
) -> ActivityCreate:
    return ActivityCreate(
        user_id=user_id,
        event_type=event_type,
        timestamp=timestamp,
        metadata=metadata,
    )


def _normal_workday(user_id: str, start: datetime) -> list[ActivityCreate]:
    return [
        _event(user_id, "LOGIN", start, {"method": "single-sign-on", "device": "managed-laptop"}),
        _event(
            user_id,
            "REPOSITORY_ACCESS",
            start + timedelta(minutes=4),
            {"repository": "internal-security-service", "action": "pull"},
        ),
        _event(
            user_id,
            "FILE_ACCESS",
            start + timedelta(minutes=18),
            {"filename": "deployment-guide.md", "source": "internal-drive"},
        ),
        _event(
            user_id,
            "API_REQUEST",
            start + timedelta(minutes=31),
            {"endpoint": "/v1/audit-events", "method": "GET", "status_code": 200},
        ),
        _event(user_id, "LOGOUT", start + timedelta(hours=7, minutes=42), {"reason": "user-initiated"}),
    ]


def _large_data_access(user_id: str, start: datetime) -> list[ActivityCreate]:
    events = [
        _event(user_id, "LOGIN", start, {"method": "single-sign-on", "device": "managed-laptop"}),
        _event(
            user_id,
            "REPOSITORY_ACCESS",
            start + timedelta(minutes=3),
            {"repository": "analytics-tooling", "action": "browse"},
        ),
    ]
    files = [
        ("customer_records_q1.csv", 240),
        ("customer_records_q2.csv", 218),
        ("customer_records_q3.csv", 231),
        ("customer_records_q4.csv", 227),
        ("account_summary.csv", 156),
    ]
    for index, (filename, size_mb) in enumerate(files):
        events.append(
            _event(
                user_id,
                "FILE_DOWNLOAD",
                start + timedelta(minutes=12 + index * 4),
                {"filename": filename, "size_mb": size_mb, "source": "internal-drive"},
            )
        )
    events.append(_event(user_id, "LOGOUT", start + timedelta(hours=1, minutes=5), {"reason": "user-initiated"}))
    return events


def _possible_data_exfiltration(user_id: str, start: datetime) -> list[ActivityCreate]:
    events = _large_data_access(user_id, start)[:-1]
    events.extend(
        [
            _event(
                user_id,
                "ARCHIVE_CREATED",
                start + timedelta(minutes=39),
                {"filename": "customer_records.zip", "source_files": 5, "size_mb": 238},
            ),
            _event(
                user_id,
                "EXTERNAL_UPLOAD",
                start + timedelta(minutes=46),
                {
                    "filename": "customer_records.zip",
                    "destination": "external-storage.example",
                    "size_mb": 238,
                },
            ),
        ]
    )
    return events


def _credential_change(user_id: str, start: datetime) -> list[ActivityCreate]:
    return [
        _event(user_id, "LOGIN", start, {"method": "single-sign-on", "device": "managed-laptop"}),
        _event(
            user_id,
            "PASSWORD_CHANGE",
            start + timedelta(minutes=6),
            {"method": "self-service", "result": "success"},
        ),
        _event(user_id, "LOGOUT", start + timedelta(minutes=11), {"reason": "user-initiated"}),
    ]


def _baseline_history(user_id: str, start: datetime) -> list[ActivityCreate]:
    """Create several completed normal sessions for a meaningful baseline."""
    return [
        event
        for days_ago in range(10, 0, -1)
        for event in _normal_workday(user_id, start - timedelta(days=days_ago))
    ]


def generate_scenario(scenario_name: str, user_id: str) -> list[ActivityCreate]:
    """Build a chronological scenario. It never writes to the database."""
    # Start in the past so even the full workday scenario never creates future events.
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=8)
    scenario_builders = {
        "normal-workday": _normal_workday,
        "baseline-history": _baseline_history,
        "large-data-access": _large_data_access,
        "possible-data-exfiltration": _possible_data_exfiltration,
        "credential-change": _credential_change,
    }
    builder = scenario_builders.get(scenario_name)
    if builder is None:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    return builder(user_id, start)
