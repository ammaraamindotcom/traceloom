"""API request and response contracts."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ActivityCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=100)
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    event_type: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(validation_alias=AliasChoices("metadata_", "metadata"))


class BehavioralBaseline(BaseModel):
    session_count: int
    average_activities_per_session: float
    average_file_downloads: float
    average_file_uploads: float
    average_repository_accesses: float
    average_database_queries: float
    average_session_duration_minutes: float
    average_downloaded_data_mb: float
    most_common_event_types: list[str]
    event_type_counts: dict[str, int]


class AnomalySignal(BaseModel):
    type: str
    description: str
    severity: str
    evidence: dict[str, Any]


class AnalysisResult(BaseModel):
    user_id: str
    risk_level: str
    risk_score: int
    signals: list[AnomalySignal]
    baseline: BehavioralBaseline
    recent_activities: list[ActivityRead]


IntentCategory = Literal[
    "NORMAL_WORK",
    "BULK_DATA_ACCESS",
    "DATA_EXFILTRATION",
    "CREDENTIAL_MODIFICATION",
    "REPOSITORY_ACTIVITY",
    "AUTOMATED_ACTIVITY",
    "UNKNOWN",
]


class IntentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    explanation: str


class IntentInference(BaseModel):
    """Constrained LLM output; evidence references are validated again in the service."""

    model_config = ConfigDict(extra="forbid")

    intent: IntentCategory
    confidence: float
    summary: str
    evidence: list[IntentEvidence]
    uncertainties: list[str]


class IntentAnalysisResult(BaseModel):
    deterministic_analysis: AnalysisResult
    intent_inference: IntentInference


class Incident(BaseModel):
    incident_id: str
    user_id: str
    created_at: datetime
    start_time: datetime
    end_time: datetime
    risk_level: str
    risk_score: int
    activity_ids: list[uuid.UUID]
    signal_types: list[str]


class TimelineEntry(BaseModel):
    activity_id: uuid.UUID
    timestamp: datetime
    event_type: str
    description: str
    transition_explanation: str | None = None


GraphNodeType = Literal["USER", "ACTIVITY", "SIGNAL", "INCIDENT", "INTENT"]


class EvidenceGraphNode(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class EvidenceGraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class EvidenceGraph(BaseModel):
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]


class IncidentInvestigationResult(BaseModel):
    incident: Incident | None
    timeline: list[TimelineEntry]
    signals: list[AnomalySignal]
    graph: EvidenceGraph
    intent: IntentInference | None = None
    deterministic_analysis: AnalysisResult


InterventionAction = Literal[
    "ALLOW",
    "MONITOR",
    "REQUIRE_REAUTHENTICATION",
    "REQUIRE_MFA",
    "RESTRICT_EXTERNAL_UPLOAD",
    "TEMPORARILY_RESTRICT_DOWNLOADS",
    "ESCALATE_TO_SECURITY",
]
PolicyDecision = Literal["ALLOW", "MONITOR", "CHALLENGE", "RESTRICT", "ESCALATE"]


class PolicyRecommendation(BaseModel):
    action: InterventionAction
    severity: str
    reason: str
    triggered_by: list[str]


class PolicyRisk(BaseModel):
    level: str
    score: int


class PolicyResult(BaseModel):
    user_id: str
    risk: PolicyRisk
    decision: PolicyDecision
    decision_severity: str
    recommendations: list[PolicyRecommendation]
    signals: list[AnomalySignal]
    deterministic_analysis: AnalysisResult


class DryRunInterventionRequest(BaseModel):
    action: InterventionAction


class DryRunInterventionResult(BaseModel):
    audit_id: uuid.UUID
    mode: Literal["DRY_RUN"]
    executed: Literal[False]
    action: InterventionAction
    effect: str
    reason: str
    triggered_by: list[str]
    affected_user: str
    created_at: datetime


class InterventionAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    action: InterventionAction
    severity: str
    reason: str
    triggered_by: list[str]
    mode: Literal["DRY_RUN"]
    executed: Literal[False]
    created_at: datetime


ScenarioClassification = Literal["BENIGN", "SUSPICIOUS"]


class EvaluationExpected(BaseModel):
    classification: ScenarioClassification
    risk_level: str
    incident: bool
    signals: list[str]
    policy_decision: PolicyDecision
    intent: IntentCategory | None = None


class EvaluationScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    expected: EvaluationExpected


class EvaluationActual(BaseModel):
    risk_level: str
    incident: bool
    signals: list[str]
    policy_decision: PolicyDecision
    intent: IntentCategory | None = None
    intent_confidence: float | None = None


class SignalEvaluation(BaseModel):
    correctly_triggered: list[str]
    missed: list[str]
    unexpected: list[str]


class EvaluationScenarioResult(BaseModel):
    scenario: EvaluationScenario
    actual: EvaluationActual
    signals: SignalEvaluation
    passed: bool
    ai_error: str | None = None


class IncidentDetectionMetrics(BaseModel):
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float


class SignalEvaluationSummary(BaseModel):
    correctly_triggered: int
    missed: int
    unexpected: int


class EvaluationRunRequest(BaseModel):
    include_ai: bool = False


class EvaluationRunResult(BaseModel):
    include_ai: bool
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    incident_detection: IncidentDetectionMetrics
    policy_accuracy: float
    signal_summary: SignalEvaluationSummary
    results: list[EvaluationScenarioResult]
