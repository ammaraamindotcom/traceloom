"""Deterministic evaluation harness over fixed synthetic telemetry."""

from collections.abc import Iterable

from app.evaluation.dataset import EVALUATION_SCENARIOS, build_scenario_activities
from app.schemas import (
    EvaluationActual,
    EvaluationRunResult,
    EvaluationScenarioResult,
    IncidentDetectionMetrics,
    SignalEvaluation,
    SignalEvaluationSummary,
)
from app.services.analysis_service import analyze_user_activities
from app.services.intent_service import IntentServiceError, infer_intent
from app.services.policy_service import evaluate_policy


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def calculate_incident_metrics(predictions: Iterable[tuple[bool, bool]]) -> IncidentDetectionMetrics:
    true_positive = true_negative = false_positive = false_negative = 0
    for expected, actual in predictions:
        if expected and actual:
            true_positive += 1
        elif not expected and not actual:
            true_negative += 1
        elif not expected and actual:
            false_positive += 1
        else:
            false_negative += 1
    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1_score = _safe_divide(2 * precision * recall, precision + recall)
    accuracy = _safe_divide(true_positive + true_negative, true_positive + true_negative + false_positive + false_negative)
    return IncidentDetectionMetrics(
        true_positives=true_positive,
        true_negatives=true_negative,
        false_positives=false_positive,
        false_negatives=false_negative,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        accuracy=accuracy,
    )


def _signal_evaluation(expected: list[str], actual: list[str]) -> SignalEvaluation:
    expected_set, actual_set = set(expected), set(actual)
    return SignalEvaluation(
        correctly_triggered=sorted(expected_set & actual_set),
        missed=sorted(expected_set - actual_set),
        unexpected=sorted(actual_set - expected_set),
    )


def run_evaluation(include_ai: bool = False) -> EvaluationRunResult:
    """Run the fixed dataset. By default this performs no OpenAI API calls."""
    results: list[EvaluationScenarioResult] = []
    incident_predictions: list[tuple[bool, bool]] = []
    policy_matches = 0
    signal_correct = signal_missed = signal_unexpected = 0

    for scenario in EVALUATION_SCENARIOS:
        activities = build_scenario_activities(scenario.scenario_id)
        user_id = activities[0].user_id
        analysis = analyze_user_activities(user_id, activities)
        policy = evaluate_policy(analysis)
        actual_signals = [signal.type for signal in analysis.signals]
        signal_result = _signal_evaluation(scenario.expected.signals, actual_signals)
        predicted_intent = confidence = None
        ai_error = None
        if include_ai and scenario.expected.intent is not None:
            try:
                inference = infer_intent(analysis)
                predicted_intent = inference.intent
                confidence = inference.confidence
            except IntentServiceError as exc:
                ai_error = exc.message

        actual = EvaluationActual(
            risk_level=analysis.risk_level,
            incident=analysis.risk_level == "high",
            signals=actual_signals,
            policy_decision=policy.decision,
            intent=predicted_intent,
            intent_confidence=confidence,
        )
        ai_matches = (
            not include_ai
            or scenario.expected.intent is None
            or (predicted_intent == scenario.expected.intent and ai_error is None)
        )
        passed = (
            scenario.expected.risk_level == actual.risk_level
            and scenario.expected.incident == actual.incident
            and scenario.expected.policy_decision == actual.policy_decision
            and not signal_result.missed
            and not signal_result.unexpected
            and ai_matches
        )
        results.append(EvaluationScenarioResult(scenario=scenario, actual=actual, signals=signal_result, passed=passed, ai_error=ai_error))
        incident_predictions.append((scenario.expected.incident, actual.incident))
        policy_matches += scenario.expected.policy_decision == actual.policy_decision
        signal_correct += len(signal_result.correctly_triggered)
        signal_missed += len(signal_result.missed)
        signal_unexpected += len(signal_result.unexpected)

    metrics = calculate_incident_metrics(incident_predictions)
    return EvaluationRunResult(
        include_ai=include_ai,
        total_scenarios=len(results),
        passed_scenarios=sum(result.passed for result in results),
        failed_scenarios=sum(not result.passed for result in results),
        incident_detection=metrics,
        policy_accuracy=_safe_divide(policy_matches, len(results)),
        signal_summary=SignalEvaluationSummary(
            correctly_triggered=signal_correct,
            missed=signal_missed,
            unexpected=signal_unexpected,
        ),
        results=results,
    )
