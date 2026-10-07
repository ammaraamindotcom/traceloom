from app.evaluation.dataset import EVALUATION_SCENARIOS
from app.schemas import IntentInference
from app.services import evaluation_service
from app.services.evaluation_service import _signal_evaluation, calculate_incident_metrics, run_evaluation


def test_evaluation_dataset_has_balanced_benign_and_suspicious_scenarios():
    classifications = [scenario.expected.classification for scenario in EVALUATION_SCENARIOS]

    assert len(EVALUATION_SCENARIOS) == 20
    assert classifications.count("BENIGN") == 10
    assert classifications.count("SUSPICIOUS") == 10
    assert all(scenario.expected.risk_level for scenario in EVALUATION_SCENARIOS)


def test_incident_metrics_and_divide_by_zero_are_safe():
    metrics = calculate_incident_metrics([(True, True), (False, False), (False, True), (True, False)])
    empty = calculate_incident_metrics([])

    assert (metrics.true_positives, metrics.true_negatives, metrics.false_positives, metrics.false_negatives) == (1, 1, 1, 1)
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1_score == 0.5
    assert metrics.accuracy == 0.5
    assert empty.precision == empty.recall == empty.f1_score == empty.accuracy == 0


def test_signal_comparison_reports_correct_missed_and_unexpected():
    comparison = _signal_evaluation(["A", "B"], ["B", "C"])

    assert comparison.correctly_triggered == ["B"]
    assert comparison.missed == ["A"]
    assert comparison.unexpected == ["C"]


def test_default_evaluation_never_calls_ai(monkeypatch):
    monkeypatch.setattr(evaluation_service, "infer_intent", lambda *args: (_ for _ in ()).throw(AssertionError("AI must not be called")))

    result = run_evaluation(include_ai=False)

    assert result.include_ai is False
    assert result.total_scenarios == 20
    assert result.incident_detection.accuracy == 1.0


def test_ai_evaluation_only_runs_for_explicit_expected_intent(monkeypatch):
    calls = []

    def fake_inference(analysis):
        calls.append(analysis.user_id)
        return IntentInference(
            intent="DATA_EXFILTRATION", confidence=0.9, summary="Mocked result.", evidence=[], uncertainties=[]
        )

    monkeypatch.setattr(evaluation_service, "infer_intent", fake_inference)

    result = run_evaluation(include_ai=True)

    expected_intent_scenarios = [scenario for scenario in EVALUATION_SCENARIOS if scenario.expected.intent is not None]
    assert len(calls) == len(expected_intent_scenarios)
    assert all(item.actual.intent == "DATA_EXFILTRATION" for item in result.results if item.scenario.expected.intent is not None)


def test_evaluation_endpoint_exposes_ground_truth_and_results(client):
    scenarios = client.get("/evaluation/scenarios")
    run = client.post("/evaluation/run", json={"include_ai": False})

    assert scenarios.status_code == 200
    assert len(scenarios.json()) == 20
    assert run.status_code == 200
    body = run.json()
    assert body["include_ai"] is False
    assert body["total_scenarios"] == 20
    assert body["passed_scenarios"] + body["failed_scenarios"] == 20
    assert all("expected" not in item for item in body["results"])
    assert all("scenario" in item and "actual" in item for item in body["results"])
