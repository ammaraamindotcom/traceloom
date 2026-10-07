from datetime import datetime

import pytest


@pytest.mark.parametrize(
    ("scenario_name", "expected_event_types"),
    [
        ("normal-workday", ["LOGIN", "REPOSITORY_ACCESS", "FILE_ACCESS", "API_REQUEST", "LOGOUT"]),
        (
            "large-data-access",
            ["LOGIN", "REPOSITORY_ACCESS", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "LOGOUT"],
        ),
        (
            "possible-data-exfiltration",
            ["LOGIN", "REPOSITORY_ACCESS", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "FILE_DOWNLOAD", "ARCHIVE_CREATED", "EXTERNAL_UPLOAD"],
        ),
        ("credential-change", ["LOGIN", "PASSWORD_CHANGE", "LOGOUT"]),
    ],
)
def test_simulate_scenario_returns_expected_sequence(client, scenario_name, expected_event_types):
    response = client.post(f"/simulate/{scenario_name}?user_id=test-user")

    assert response.status_code == 201
    activities = response.json()
    assert [activity["event_type"] for activity in activities] == expected_event_types
    assert {activity["user_id"] for activity in activities} == {"test-user"}


def test_simulated_activity_timestamps_are_chronological(client):
    response = client.post("/simulate/possible-data-exfiltration")

    timestamps = [datetime.fromisoformat(activity["timestamp"]) for activity in response.json()]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps)


def test_invalid_scenario_name_returns_not_found(client):
    response = client.post("/simulate/not-a-scenario")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown scenario: not-a-scenario"


def test_activities_can_be_filtered_by_user_id(client):
    client.post("/simulate/credential-change?user_id=alex")
    client.post("/simulate/normal-workday?user_id=blair")

    response = client.get("/activities?user_id=alex")

    assert response.status_code == 200
    activities = response.json()
    assert len(activities) == 3
    assert {activity["user_id"] for activity in activities} == {"alex"}
