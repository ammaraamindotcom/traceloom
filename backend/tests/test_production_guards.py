from app.services import rate_limit_service
from app.services.rate_limit_service import SlidingWindowLimiter


def test_sliding_window_limiter_enforces_request_cap():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)

    assert limiter.allow("demo-client") is True
    assert limiter.allow("demo-client") is False
    assert limiter.allow("another-client") is True


def test_production_intent_endpoints_require_server_side_token(client, monkeypatch):
    monkeypatch.setattr(rate_limit_service, "IS_PRODUCTION", True)
    monkeypatch.setattr(rate_limit_service, "INTENT_ACCESS_TOKEN", "test-operator-token")

    denied_intent = client.get("/intent/no-activities")
    allowed_intent = client.get(
        "/intent/no-activities", headers={"X-TraceLoom-Intent-Token": "test-operator-token"}
    )
    denied_ai_evaluation = client.post("/evaluation/run", json={"include_ai": True})

    assert denied_intent.status_code == 403
    # The request passes the protection layer and then correctly finds no telemetry.
    assert allowed_intent.status_code == 404
    assert denied_ai_evaluation.status_code == 403
