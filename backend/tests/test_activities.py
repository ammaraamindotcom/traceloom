def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_activity(client):
    response = client.post(
        "/activities",
        json={
            "user_id": "student-123",
            "event_type": "file_download",
            "metadata": {"file_name": "notes.pdf"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == "student-123"
    assert body["event_type"] == "file_download"
    assert body["metadata"] == {"file_name": "notes.pdf"}
    assert "id" in body


def test_list_activities_returns_recent_records(client):
    client.post(
        "/activities",
        json={"user_id": "student-123", "event_type": "login", "metadata": {}},
    )

    response = client.get("/activities")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["event_type"] == "login"
