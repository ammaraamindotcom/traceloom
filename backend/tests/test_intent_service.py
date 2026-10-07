from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import httpx

from app.schemas import (
    ActivityRead,
    AnalysisResult,
    AnomalySignal,
    BehavioralBaseline,
    IntentEvidence,
    IntentInference,
)
from app.services import intent_service
from app.services.intent_service import IntentServiceError, build_intent_input, infer_intent


def analysis_result(signals=None):
    return AnalysisResult(
        user_id="investigation-user",
        risk_level="high" if signals else "low",
        risk_score=6 if signals else 0,
        signals=signals or [],
        baseline=BehavioralBaseline(
            session_count=5,
            average_activities_per_session=5,
            average_file_downloads=1,
            average_file_uploads=0,
            average_repository_accesses=1,
            average_database_queries=0,
            average_session_duration_minutes=60,
            average_downloaded_data_mb=20,
            most_common_event_types=["LOGIN"],
            event_type_counts={"LOGIN": 5},
        ),
        recent_activities=[
            ActivityRead(
                id=uuid4(),
                user_id="investigation-user",
                event_type="FILE_DOWNLOAD",
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                metadata={"filename": "customer_records.csv", "size_mb": 240},
            )
        ],
    )


class FakeClient:
    def __init__(self, parsed):
        self.completions = SimpleNamespace(parse=self.parse)
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=self.completions))
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=self.parsed, refusal=None))])


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    monkeypatch.setattr(intent_service, "OPENAI_API_KEY", "test-key")


def test_builds_minimal_structured_input_without_environment_data():
    signals = [AnomalySignal(type="HIGH_DOWNLOAD_VOLUME", description="", severity="high", evidence={"downloads": 5})]

    payload = build_intent_input(analysis_result(signals))

    assert set(payload) == {"user_id", "deterministic_risk", "behavioral_baseline", "deterministic_signals", "recent_activity_sequence"}
    assert payload["deterministic_signals"][0]["type"] == "HIGH_DOWNLOAD_VOLUME"
    assert "OPENAI_API_KEY" not in str(payload)


@pytest.mark.parametrize(
    ("intent", "signals"),
    [
        ("DATA_EXFILTRATION", [AnomalySignal(type="EXTERNAL_UPLOAD_AFTER_DOWNLOADS", description="", severity="high", evidence={})]),
        ("NORMAL_WORK", []),
        ("UNKNOWN", []),
    ],
)
def test_accepts_valid_structured_intent_categories(intent, signals):
    response = IntentInference(
        intent=intent,
        confidence=0.8,
        summary="Potential intent based on supplied telemetry.",
        evidence=[IntentEvidence(signal=signals[0].type, explanation="Supplied signal supports this interpretation.")] if signals else [],
        uncertainties=["Authorization context is unavailable."],
    )
    client = FakeClient(response)

    result = infer_intent(analysis_result(signals), client=client)

    assert result.intent == intent
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert client.calls[0]["messages"][1]["content"].startswith("UNTRUSTED_TELEMETRY_JSON")


def test_rejects_malformed_provider_response():
    client = FakeClient({"not": "a validated intent schema"})

    with pytest.raises(IntentServiceError, match="invalid structured result"):
        infer_intent(analysis_result(), client=client)


def test_rejects_evidence_not_supplied_by_deterministic_layer():
    response = IntentInference(
        intent="DATA_EXFILTRATION",
        confidence=0.9,
        summary="Potentially risky pattern.",
        evidence=[IntentEvidence(signal="INVENTED_SIGNAL", explanation="Not valid")],
        uncertainties=[],
    )

    with pytest.raises(IntentServiceError, match="not present"):
        infer_intent(analysis_result(), client=FakeClient(response))


def test_rejects_invalid_confidence():
    response = IntentInference(
        intent="UNKNOWN", confidence=1.5, summary="", evidence=[], uncertainties=[]
    )

    with pytest.raises(IntentServiceError, match="confidence"):
        infer_intent(analysis_result(), client=FakeClient(response))


def test_reports_missing_api_key(monkeypatch):
    monkeypatch.setattr(intent_service, "OPENAI_API_KEY", None)

    with pytest.raises(IntentServiceError, match="OPENAI_API_KEY") as error:
        infer_intent(analysis_result(), client=FakeClient(None))

    assert error.value.status_code == 503


def test_reports_provider_api_failure_without_logging_secrets(caplog):
    class FailingClient(FakeClient):
        def parse(self, **kwargs):
            raise intent_service.APIConnectionError(
                message="authorization: Bearer sk-secret-test unavailable",
                request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            )

    with pytest.raises(IntentServiceError, match="temporarily unavailable"):
        infer_intent(analysis_result(), client=FailingClient(None))

    assert "APIConnectionError" in caplog.text
    assert "sk-secret-test" not in caplog.text
    assert "Bearer sk" not in caplog.text


def test_intent_endpoint_combines_deterministic_and_inference_layers(client, monkeypatch):
    response = IntentInference(
        intent="NORMAL_WORK", confidence=0.7, summary="The session is consistent with routine work.", evidence=[], uncertainties=[]
    )
    monkeypatch.setattr("app.routes.intent.infer_intent", lambda analysis: response)
    client.post("/simulate/baseline-history?user_id=intent-user")
    client.post("/simulate/normal-workday?user_id=intent-user")

    result = client.get("/intent/intent-user")

    assert result.status_code == 200
    assert result.json()["intent_inference"]["intent"] == "NORMAL_WORK"
    assert result.json()["deterministic_analysis"]["risk_level"] == "low"
