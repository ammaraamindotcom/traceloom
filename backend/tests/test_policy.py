from datetime import datetime, timedelta, timezone

from app.schemas import PolicyRecommendation
from app.services import intent_service
from app.services.policy_service import _overall_decision


def prepare_high_risk_user(client, user_id: str):
    client.post(f"/simulate/baseline-history?user_id={user_id}")
    client.post(f"/simulate/possible-data-exfiltration?user_id={user_id}")


def prepare_medium_risk_user(client, user_id: str):
    client.post(f"/simulate/baseline-history?user_id={user_id}")
    start = datetime.now(timezone.utc).replace(microsecond=0)
    events = [{"user_id": user_id, "event_type": "LOGIN", "timestamp": start.isoformat(), "metadata": {}}]
    events.extend(
        {
            "user_id": user_id,
            "event_type": "FILE_DOWNLOAD",
            "timestamp": (start + timedelta(minutes=index + 1)).isoformat(),
            "metadata": {"filename": f"report-{index}.csv"},
        }
        for index in range(5)
    )
    for event in events:
        assert client.post("/activities", json=event).status_code == 201


def test_low_risk_policy_allows_normal_activity(client):
    client.post("/simulate/baseline-history?user_id=policy-normal")
    client.post("/simulate/normal-workday?user_id=policy-normal")

    response = client.get("/policy/policy-normal")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["recommendations"][0]["action"] == "ALLOW"


def test_medium_risk_policy_monitors(client):
    prepare_medium_risk_user(client, "policy-medium")

    body = client.get("/policy/policy-medium").json()

    assert body["risk"]["level"] == "medium"
    assert body["decision"] == "MONITOR"
    assert body["recommendations"][0]["action"] == "MONITOR"


def test_exfiltration_policy_recommends_restrictions_and_escalation(client):
    prepare_high_risk_user(client, "policy-high")

    body = client.get("/policy/policy-high").json()

    actions = {item["action"] for item in body["recommendations"]}
    signal_types = {signal["type"] for signal in body["signals"]}
    assert body["decision"] == "ESCALATE"
    assert {"TEMPORARILY_RESTRICT_DOWNLOADS", "RESTRICT_EXTERNAL_UPLOAD", "ESCALATE_TO_SECURITY"} <= actions
    assert all(set(item["triggered_by"]) <= signal_types for item in body["recommendations"])


def test_suspicious_password_change_recommends_mfa_when_high_risk(client):
    prepare_high_risk_user(client, "policy-credential")
    client.post(
        "/activities",
        json={
            "user_id": "policy-credential",
            "event_type": "PASSWORD_CHANGE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"method": "self-service"},
        },
    )

    body = client.get("/policy/policy-credential").json()

    assert "REQUIRE_MFA" in {item["action"] for item in body["recommendations"]}


def test_overall_decision_precedence():
    recommendations = [
        PolicyRecommendation(action="MONITOR", severity="medium", reason="", triggered_by=[]),
        PolicyRecommendation(action="REQUIRE_REAUTHENTICATION", severity="medium", reason="", triggered_by=[]),
        PolicyRecommendation(action="RESTRICT_EXTERNAL_UPLOAD", severity="high", reason="", triggered_by=[]),
        PolicyRecommendation(action="ESCALATE_TO_SECURITY", severity="high", reason="", triggered_by=[]),
    ]

    assert _overall_decision(recommendations) == ("ESCALATE", "high")


def test_policy_is_deterministic_and_never_invokes_openai(client, monkeypatch):
    prepare_high_risk_user(client, "policy-no-ai")
    monkeypatch.setattr(intent_service, "infer_intent", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("AI must not be called")))

    first = client.get("/policy/policy-no-ai").json()
    second = client.get("/policy/policy-no-ai").json()

    assert first["decision"] == second["decision"]
    assert first["recommendations"] == second["recommendations"]


def test_valid_dry_run_creates_audit_entry_and_unsupported_action_is_rejected(client):
    prepare_high_risk_user(client, "policy-audit")

    dry_run = client.post("/policy/policy-audit/simulate", json={"action": "RESTRICT_EXTERNAL_UPLOAD"})

    assert dry_run.status_code == 201
    result = dry_run.json()
    assert result["mode"] == "DRY_RUN"
    assert result["executed"] is False
    assert result["affected_user"] == "policy-audit"

    audit = client.get("/policy/policy-audit/audit")
    assert audit.status_code == 200
    assert len(audit.json()) == 1
    assert audit.json()[0]["action"] == "RESTRICT_EXTERNAL_UPLOAD"
    assert audit.json()[0]["executed"] is False

    unsupported = client.post("/policy/policy-audit/simulate", json={"action": "REQUIRE_MFA"})
    assert unsupported.status_code == 400
