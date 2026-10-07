from datetime import datetime, timedelta, timezone

from app.services import intent_service


def create_medium_download_session(client, user_id: str):
    base_time = datetime.now(timezone.utc).replace(microsecond=0)
    events = [
        {"user_id": user_id, "event_type": "LOGIN", "timestamp": base_time.isoformat(), "metadata": {}},
        *[
            {
                "user_id": user_id,
                "event_type": "FILE_DOWNLOAD",
                "timestamp": (base_time + timedelta(minutes=index + 1)).isoformat(),
                "metadata": {"filename": f"report-{index}.csv"},
            }
            for index in range(5)
        ],
    ]
    for event in events:
        assert client.post("/activities", json=event).status_code == 201


def test_high_risk_sequence_creates_incident_with_real_evidence(client):
    client.post("/simulate/baseline-history?user_id=investigation-user")
    client.post("/simulate/possible-data-exfiltration?user_id=investigation-user")

    response = client.get("/incidents/investigation-user")

    assert response.status_code == 200
    body = response.json()
    incident = body["incident"]
    assert incident["user_id"] == "investigation-user"
    assert incident["risk_level"] == "high"
    assert incident["incident_id"] == "incident-investigation-user"
    assert incident["start_time"] == body["timeline"][0]["timestamp"]
    assert incident["end_time"] == body["timeline"][-1]["timestamp"]
    assert body["intent"] is None

    timeline_activity_ids = {entry["activity_id"] for entry in body["timeline"]}
    graph_activity_ids = {
        node["data"]["activity_id"]
        for node in body["graph"]["nodes"]
        if node["type"] == "ACTIVITY"
    }
    graph_signal_labels = {node["label"] for node in body["graph"]["nodes"] if node["type"] == "SIGNAL"}
    assert graph_activity_ids == timeline_activity_ids == set(incident["activity_ids"])
    assert graph_signal_labels == {signal["type"] for signal in body["signals"]}
    assert [entry["timestamp"] for entry in body["timeline"]] == sorted(entry["timestamp"] for entry in body["timeline"])
    assert any(entry["transition_explanation"] for entry in body["timeline"])


def test_low_risk_sequence_returns_clean_no_incident_response(client):
    client.post("/simulate/baseline-history?user_id=normal-user")
    client.post("/simulate/normal-workday?user_id=normal-user")

    response = client.get("/incidents/normal-user")

    assert response.status_code == 200
    body = response.json()
    assert body["incident"] is None
    assert body["timeline"] == []
    assert body["graph"] == {"nodes": [], "edges": []}
    assert body["intent"] is None


def test_medium_risk_sequence_does_not_create_incident(client):
    client.post("/simulate/baseline-history?user_id=medium-user")
    create_medium_download_session(client, "medium-user")

    response = client.get("/incidents/medium-user")

    assert response.status_code == 200
    assert response.json()["deterministic_analysis"]["risk_level"] == "medium"
    assert response.json()["incident"] is None


def test_graph_edges_only_connect_real_activities_to_real_signals(client):
    client.post("/simulate/baseline-history?user_id=edge-user")
    client.post("/simulate/possible-data-exfiltration?user_id=edge-user")

    body = client.get("/incidents/edge-user").json()
    node_types = {node["id"]: node["type"] for node in body["graph"]["nodes"]}
    supports_edges = [edge for edge in body["graph"]["edges"] if edge["relationship"] == "supports"]
    assert supports_edges
    assert all(node_types[edge["source"]] == "ACTIVITY" for edge in supports_edges)
    assert all(node_types[edge["target"]] == "SIGNAL" for edge in supports_edges)


def test_incident_endpoint_does_not_invoke_openai(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("OpenAI must not be called by incident investigation")

    monkeypatch.setattr(intent_service, "infer_intent", fail_if_called)
    client.post("/simulate/baseline-history?user_id=no-ai-user")
    client.post("/simulate/possible-data-exfiltration?user_id=no-ai-user")

    response = client.get("/incidents/no-ai-user")

    assert response.status_code == 200
    assert response.json()["intent"] is None
