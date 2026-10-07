import { request } from "./client";

export type Activity = {
  id: string;
  user_id: string;
  event_type: string;
  timestamp: string;
  metadata: Record<string, unknown>;
};

export type AnomalySignal = {
  type: string;
  description: string;
  severity: "low" | "medium" | "high";
  evidence: Record<string, unknown>;
};

export type BehavioralBaseline = {
  session_count: number;
  average_activities_per_session: number;
  average_file_downloads: number;
  average_file_uploads: number;
  average_repository_accesses: number;
  average_database_queries: number;
  average_session_duration_minutes: number;
  average_downloaded_data_mb: number;
  most_common_event_types: string[];
  event_type_counts: Record<string, number>;
};

export type AnalysisResult = {
  user_id: string;
  risk_level: "low" | "medium" | "high";
  risk_score: number;
  signals: AnomalySignal[];
  baseline: BehavioralBaseline;
  recent_activities: Activity[];
};

export type IntentEvidence = {
  signal: string;
  explanation: string;
};

export type IntentInference = {
  intent: "NORMAL_WORK" | "BULK_DATA_ACCESS" | "DATA_EXFILTRATION" | "CREDENTIAL_MODIFICATION" | "REPOSITORY_ACTIVITY" | "AUTOMATED_ACTIVITY" | "UNKNOWN";
  confidence: number;
  summary: string;
  evidence: IntentEvidence[];
  uncertainties: string[];
};

export type IntentAnalysisResult = {
  deterministic_analysis: AnalysisResult;
  intent_inference: IntentInference;
};

export type Incident = {
  incident_id: string;
  user_id: string;
  created_at: string;
  start_time: string;
  end_time: string;
  risk_level: string;
  risk_score: number;
  activity_ids: string[];
  signal_types: string[];
};

export type TimelineEntry = {
  activity_id: string;
  timestamp: string;
  event_type: string;
  description: string;
  transition_explanation: string | null;
};

export type EvidenceGraphNode = {
  id: string;
  type: "USER" | "ACTIVITY" | "SIGNAL" | "INCIDENT" | "INTENT";
  label: string;
  data: Record<string, unknown>;
};

export type EvidenceGraphEdge = {
  source: string;
  target: string;
  relationship: string;
};

export type IncidentInvestigationResult = {
  incident: Incident | null;
  timeline: TimelineEntry[];
  signals: AnomalySignal[];
  graph: { nodes: EvidenceGraphNode[]; edges: EvidenceGraphEdge[] };
  intent: IntentInference | null;
  deterministic_analysis: AnalysisResult;
};

export type InterventionAction =
  | "ALLOW"
  | "MONITOR"
  | "REQUIRE_REAUTHENTICATION"
  | "REQUIRE_MFA"
  | "RESTRICT_EXTERNAL_UPLOAD"
  | "TEMPORARILY_RESTRICT_DOWNLOADS"
  | "ESCALATE_TO_SECURITY";

export type PolicyRecommendation = {
  action: InterventionAction;
  severity: string;
  reason: string;
  triggered_by: string[];
};

export type PolicyResult = {
  user_id: string;
  risk: { level: string; score: number };
  decision: "ALLOW" | "MONITOR" | "CHALLENGE" | "RESTRICT" | "ESCALATE";
  decision_severity: string;
  recommendations: PolicyRecommendation[];
  signals: AnomalySignal[];
  deterministic_analysis: AnalysisResult;
};

export type DryRunInterventionResult = {
  audit_id: string;
  mode: "DRY_RUN";
  executed: false;
  action: InterventionAction;
  effect: string;
  reason: string;
  triggered_by: string[];
  affected_user: string;
  created_at: string;
};

export type InterventionAudit = {
  id: string;
  user_id: string;
  action: InterventionAction;
  severity: string;
  reason: string;
  triggered_by: string[];
  mode: "DRY_RUN";
  executed: false;
  created_at: string;
};

export type EvaluationScenario = {
  scenario_id: string;
  name: string;
  description: string;
  expected: {
    classification: "BENIGN" | "SUSPICIOUS";
    risk_level: string;
    incident: boolean;
    signals: string[];
    policy_decision: string;
    intent: string | null;
  };
};

export type EvaluationScenarioResult = {
  scenario: EvaluationScenario;
  actual: {
    risk_level: string;
    incident: boolean;
    signals: string[];
    policy_decision: string;
    intent: string | null;
    intent_confidence: number | null;
  };
  signals: { correctly_triggered: string[]; missed: string[]; unexpected: string[] };
  passed: boolean;
  ai_error: string | null;
};

export type EvaluationRunResult = {
  include_ai: boolean;
  total_scenarios: number;
  passed_scenarios: number;
  failed_scenarios: number;
  incident_detection: {
    true_positives: number;
    true_negatives: number;
    false_positives: number;
    false_negatives: number;
    precision: number;
    recall: number;
    f1_score: number;
    accuracy: number;
  };
  policy_accuracy: number;
  signal_summary: { correctly_triggered: number; missed: number; unexpected: number };
  results: EvaluationScenarioResult[];
};

export const getActivities = (userId?: string) =>
  request<Activity[]>(`/activities${userId ? `?user_id=${encodeURIComponent(userId)}` : ""}`);
export const getHealth = () => request<{ status: string }>("/health");
export const simulateScenario = (scenarioName: string, userId: string) =>
  request<Activity[]>(`/simulate/${scenarioName}?user_id=${encodeURIComponent(userId)}`, { method: "POST" });
export const getAnalysis = (userId: string) =>
  request<AnalysisResult>(`/analysis/${encodeURIComponent(userId)}`);
export const getIntentAnalysis = (userId: string) =>
  request<IntentAnalysisResult>(`/intent/${encodeURIComponent(userId)}`);
export const getIncidentInvestigation = (userId: string) =>
  request<IncidentInvestigationResult>(`/incidents/${encodeURIComponent(userId)}`);
export const getPolicy = (userId: string) => request<PolicyResult>(`/policy/${encodeURIComponent(userId)}`);
export const simulatePolicy = (userId: string, action: InterventionAction) =>
  request<DryRunInterventionResult>(`/policy/${encodeURIComponent(userId)}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
export const getPolicyAudit = (userId: string) =>
  request<InterventionAudit[]>(`/policy/${encodeURIComponent(userId)}/audit`);
export const runEvaluation = (includeAi: boolean) =>
  request<EvaluationRunResult>("/evaluation/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_ai: includeAi }),
  });
