import { useEffect, useState } from "react";

import {
  getActivities,
  getAnalysis,
  getHealth,
  getIntentAnalysis,
  getIncidentInvestigation,
  getPolicy,
  getPolicyAudit,
  simulateScenario,
  simulatePolicy,
  runEvaluation,
  type Activity,
  type AnalysisResult,
  type IntentAnalysisResult,
  type IncidentInvestigationResult,
  type InterventionAction,
  type InterventionAudit,
  type PolicyResult,
  type DryRunInterventionResult,
  type EvaluationRunResult,
} from "../api/activities";
import { ActivityTable } from "../components/ActivityTable";

type ConnectionStatus = "checking" | "connected" | "unavailable";

export function DashboardPage() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [selectedUser, setSelectedUser] = useState("normal-user");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [intentAnalysis, setIntentAnalysis] = useState<IntentAnalysisResult | null>(null);
  const [isInferringIntent, setIsInferringIntent] = useState(false);
  const [investigation, setInvestigation] = useState<IncidentInvestigationResult | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [policy, setPolicy] = useState<PolicyResult | null>(null);
  const [auditHistory, setAuditHistory] = useState<InterventionAudit[]>([]);
  const [dryRun, setDryRun] = useState<DryRunInterventionResult | null>(null);
  const [isLoadingPolicy, setIsLoadingPolicy] = useState(false);
  const [isSimulatingPolicy, setIsSimulatingPolicy] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluationRunResult | null>(null);
  const [includeAiEvaluation, setIncludeAiEvaluation] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [health, recentActivities] = await Promise.all([getHealth(), getActivities()]);
        setStatus(health.status === "ok" ? "connected" : "unavailable");
        setActivities(recentActivities);
      } catch {
        setStatus("unavailable");
        setError("The backend could not be reached. Start the FastAPI server and refresh.");
      }
    }

    void loadDashboard();
  }, []);

  async function handleSimulation(scenarioName: string) {
    setIsSimulating(true);
    setError(null);
    try {
      await simulateScenario(scenarioName, selectedUser);
      setActivities(await getActivities(selectedUser));
    } catch {
      setError("The scenario could not be generated. Confirm the backend is running and try again.");
    } finally {
      setIsSimulating(false);
    }
  }

  async function handleAnalysis() {
    setIsAnalyzing(true);
    setError(null);
    try {
      setAnalysis(await getAnalysis(selectedUser));
    } catch {
      setAnalysis(null);
      setError("No analysis is available yet. Generate activity for the selected user first.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleIntentAnalysis() {
    setIsInferringIntent(true);
    setError(null);
    try {
      const result = await getIntentAnalysis(selectedUser);
      setIntentAnalysis(result);
      setAnalysis(result.deterministic_analysis);
    } catch {
      setIntentAnalysis(null);
      setError("Intent inference was unavailable. Confirm the backend has OPENAI_API_KEY and the OpenAI SDK installed.");
    } finally {
      setIsInferringIntent(false);
    }
  }

  async function handleInvestigation() {
    setIsInvestigating(true);
    setError(null);
    try {
      const result = await getIncidentInvestigation(selectedUser);
      setInvestigation(result);
      setAnalysis(result.deterministic_analysis);
    } catch {
      setInvestigation(null);
      setError("No incident investigation is available yet. Generate activity for the selected user first.");
    } finally {
      setIsInvestigating(false);
    }
  }

  async function handlePolicy() {
    setIsLoadingPolicy(true);
    setError(null);
    try {
      const [policyResult, audits] = await Promise.all([getPolicy(selectedUser), getPolicyAudit(selectedUser)]);
      setPolicy(policyResult);
      setAuditHistory(audits);
      setAnalysis(policyResult.deterministic_analysis);
    } catch {
      setPolicy(null);
      setError("No deterministic policy is available yet. Generate activity for the selected user first.");
    } finally {
      setIsLoadingPolicy(false);
    }
  }

  async function handlePolicySimulation(action: InterventionAction) {
    setIsSimulatingPolicy(true);
    setError(null);
    try {
      const result = await simulatePolicy(selectedUser, action);
      setDryRun(result);
      setAuditHistory(await getPolicyAudit(selectedUser));
    } catch {
      setError("The selected intervention is not currently recommended for this user.");
    } finally {
      setIsSimulatingPolicy(false);
    }
  }

  async function handleEvaluation() {
    setIsEvaluating(true);
    setError(null);
    try {
      setEvaluation(await runEvaluation(includeAiEvaluation));
    } catch {
      setError("Evaluation could not be completed. If AI evaluation is enabled, confirm model access and available API credits.");
    } finally {
      setIsEvaluating(false);
    }
  }

  return (
    <main>
      <h1>IntentShield</h1>
      <p>
        Backend connection: <strong>{status}</strong>
      </p>
      <section aria-labelledby="simulator-heading">
        <h2 id="simulator-heading">Simulate scenario</h2>
        <label>
          Simulated user
          <select value={selectedUser} onChange={(event) => setSelectedUser(event.target.value)}>
            <option value="normal-user">Normal user</option>
            <option value="investigation-user">Investigation user</option>
            <option value="simulated-user">General simulated user</option>
          </select>
        </label>
        <div className="scenario-buttons">
          <button disabled={isSimulating} onClick={() => void handleSimulation("baseline-history")}>Generate Historical Baseline</button>
          <button disabled={isSimulating} onClick={() => void handleSimulation("normal-workday")}>Normal Workday</button>
          <button disabled={isSimulating} onClick={() => void handleSimulation("large-data-access")}>Large Data Access</button>
          <button disabled={isSimulating} onClick={() => void handleSimulation("possible-data-exfiltration")}>Possible Data Exfiltration</button>
          <button disabled={isSimulating} onClick={() => void handleSimulation("credential-change")}>Credential Change</button>
        </div>
      </section>
      <section className="analysis-section" aria-labelledby="analysis-heading">
        <div className="section-heading">
          <h2 id="analysis-heading">Security analysis</h2>
          <button disabled={isAnalyzing} onClick={() => void handleAnalysis()}>Analyze selected user</button>
        </div>
        {analysis && (
          <div>
            <p>
              User: <strong>{analysis.user_id}</strong> · Risk level: <strong className={`risk-${analysis.risk_level}`}>{analysis.risk_level.toUpperCase()}</strong> · Deterministic score: {analysis.risk_score}
            </p>
            <h3>Detected signals</h3>
            {analysis.signals.length === 0 ? <p>No anomalous signals detected in the latest session.</p> : (
              <ul className="signal-list">
                {analysis.signals.map((signal) => (
                  <li key={signal.type}>
                    <strong>{signal.type}</strong> <span className={`severity-${signal.severity}`}>{signal.severity}</span>
                    <div>{signal.description}</div>
                    <code>{JSON.stringify(signal.evidence)}</code>
                  </li>
                ))}
              </ul>
            )}
            <h3>Behavioral baseline</h3>
            <dl className="baseline-grid">
              <div><dt>Historical sessions</dt><dd>{analysis.baseline.session_count}</dd></div>
              <div><dt>Activities / session</dt><dd>{analysis.baseline.average_activities_per_session}</dd></div>
              <div><dt>Downloads / session</dt><dd>{analysis.baseline.average_file_downloads}</dd></div>
              <div><dt>Downloaded MB / session</dt><dd>{analysis.baseline.average_downloaded_data_mb}</dd></div>
              <div><dt>Session duration</dt><dd>{analysis.baseline.average_session_duration_minutes} min</dd></div>
              <div><dt>Common events</dt><dd>{analysis.baseline.most_common_event_types.join(", ") || "None"}</dd></div>
            </dl>
          </div>
        )}
      </section>
      <section className="incident-section" aria-labelledby="incident-heading">
        <div className="section-heading">
          <div>
            <h2 id="incident-heading">Incident investigation</h2>
            <p>Derived only from deterministic telemetry analysis. This does not call AI inference.</p>
          </div>
          <button disabled={isInvestigating} onClick={() => void handleInvestigation()}>Investigate Incident</button>
        </div>
        {investigation && (investigation.incident ? (
          <div className="investigation-result">
            <h3>Incident overview</h3>
            <dl className="baseline-grid">
              <div><dt>Incident ID</dt><dd>{investigation.incident.incident_id}</dd></div>
              <div><dt>User</dt><dd>{investigation.incident.user_id}</dd></div>
              <div><dt>Risk level</dt><dd className={`risk-${investigation.incident.risk_level}`}>{investigation.incident.risk_level.toUpperCase()}</dd></div>
              <div><dt>Risk score</dt><dd>{investigation.incident.risk_score}</dd></div>
              <div><dt>Start time</dt><dd>{new Date(investigation.incident.start_time).toLocaleString()}</dd></div>
              <div><dt>End time</dt><dd>{new Date(investigation.incident.end_time).toLocaleString()}</dd></div>
            </dl>
            <h3>Activity timeline</h3>
            <ol className="timeline">
              {investigation.timeline.map((entry) => (
                <li key={entry.activity_id}>
                  <time>{new Date(entry.timestamp).toLocaleTimeString()}</time>
                  <strong>{entry.event_type}</strong> — {entry.description}
                  {entry.transition_explanation && <p>{entry.transition_explanation}</p>}
                </li>
              ))}
            </ol>
            <h3>Deterministic signals</h3>
            <ul className="signal-list">
              {investigation.signals.map((signal) => (
                <li key={signal.type}>
                  <strong>{signal.type}</strong> <span className={`severity-${signal.severity}`}>{signal.severity}</span>
                  <div>{signal.description}</div>
                </li>
              ))}
            </ul>
            <h3>Evidence graph</h3>
            <div className="evidence-graph">
              <div className="graph-nodes">
                {investigation.graph.nodes.map((node) => (
                  <span key={node.id} className={`graph-node graph-${node.type.toLowerCase()}`}>{node.label}</span>
                ))}
              </div>
              <ul className="graph-edges">
                {investigation.graph.edges.map((edge) => (
                  <li key={`${edge.source}-${edge.target}-${edge.relationship}`}>
                    {edge.source} <span>→ {edge.relationship} →</span> {edge.target}
                  </li>
                ))}
              </ul>
            </div>
            <h3>AI intent inference</h3>
            {investigation.intent ? <p>{investigation.intent.intent}</p> : <p>AI intent inference has not been generated.</p>}
          </div>
        ) : (
          <p>No high-risk incident exists for this user's latest session. Deterministic analysis remains available above.</p>
        ))}
      </section>
      <section className="policy-section" aria-labelledby="policy-heading">
        <div className="section-heading">
          <div>
            <h2 id="policy-heading">Policy &amp; response</h2>
            <p>Deterministic recommendations only. All simulations are dry runs and do not change any system.</p>
          </div>
          <button disabled={isLoadingPolicy} onClick={() => void handlePolicy()}>Evaluate Policy</button>
        </div>
        {policy && (
          <div>
            <h3>Security decision</h3>
            <p className={`policy-decision policy-${policy.decision.toLowerCase()}`}>
              {policy.decision} <span>{policy.decision_severity} severity</span>
            </p>
            <h3>Recommended actions</h3>
            <div className="recommendations">
              {policy.recommendations.map((recommendation) => (
                <article key={recommendation.action} className="recommendation-card">
                  <h4>{recommendation.action.replaceAll("_", " ")}</h4>
                  <p><span className={`severity-${recommendation.severity}`}>{recommendation.severity}</span> — {recommendation.reason}</p>
                  <p className="evidence-label">Deterministic evidence: {recommendation.triggered_by.join(", ") || "No elevated signals"}</p>
                  <button disabled={isSimulatingPolicy} onClick={() => void handlePolicySimulation(recommendation.action)}>Simulate Intervention</button>
                </article>
              ))}
            </div>
            {dryRun && (
              <div className="dry-run-result">
                <strong>DRY RUN — NO ACTION EXECUTED</strong>
                <p>{dryRun.effect}</p>
                <small>Action: {dryRun.action} · executed: {String(dryRun.executed)}</small>
              </div>
            )}
            <h3>Audit history</h3>
            {auditHistory.length === 0 ? <p>No simulated interventions recorded.</p> : (
              <ul className="audit-history">
                {auditHistory.map((entry) => (
                  <li key={entry.id}>
                    <time>{new Date(entry.created_at).toLocaleString()}</time> <strong>{entry.action}</strong> — {entry.reason} <span>executed: {String(entry.executed)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
      <section className="evaluation-section" aria-labelledby="evaluation-heading">
        <div className="section-heading">
          <div>
            <h2 id="evaluation-heading">Evaluation</h2>
            <p>Fixed synthetic scenarios compare explicit ground truth with deterministic system output.</p>
          </div>
          <button disabled={isEvaluating} onClick={() => void handleEvaluation()}>Run Evaluation</button>
        </div>
        <label className="ai-evaluation-toggle">
          <input type="checkbox" checked={includeAiEvaluation} onChange={(event) => setIncludeAiEvaluation(event.target.checked)} />
          Include AI intent evaluation
        </label>
        <p className="helper-text">Off by default. Enabling AI evaluation makes live model API requests and may incur API usage costs.</p>
        {evaluation && (
          <div>
            <h3>Detection performance</h3>
            <dl className="baseline-grid">
              <div><dt>Accuracy</dt><dd>{Math.round(evaluation.incident_detection.accuracy * 100)}%</dd></div>
              <div><dt>Precision</dt><dd>{Math.round(evaluation.incident_detection.precision * 100)}%</dd></div>
              <div><dt>Recall</dt><dd>{Math.round(evaluation.incident_detection.recall * 100)}%</dd></div>
              <div><dt>F1 score</dt><dd>{Math.round(evaluation.incident_detection.f1_score * 100)}%</dd></div>
              <div><dt>Policy accuracy</dt><dd>{Math.round(evaluation.policy_accuracy * 100)}%</dd></div>
            </dl>
            <h3>Confusion matrix</h3>
            <div className="confusion-matrix">
              <div><strong>True positive</strong><span>{evaluation.incident_detection.true_positives}</span></div>
              <div><strong>False positive</strong><span>{evaluation.incident_detection.false_positives}</span></div>
              <div><strong>False negative</strong><span>{evaluation.incident_detection.false_negatives}</span></div>
              <div><strong>True negative</strong><span>{evaluation.incident_detection.true_negatives}</span></div>
            </div>
            <p>Scenarios: {evaluation.total_scenarios} · Passed: {evaluation.passed_scenarios} · Failed: {evaluation.failed_scenarios}</p>
            <h3>Scenario results</h3>
            <div className="evaluation-results">
              {evaluation.results.map((result) => (
                <details key={result.scenario.scenario_id} className={result.passed ? "evaluation-pass" : "evaluation-fail"}>
                  <summary><strong>{result.passed ? "PASS" : "FAIL"}</strong> — {result.scenario.name}</summary>
                  <p>{result.scenario.description}</p>
                  <p>Ground truth: {result.scenario.expected.classification} · Expected/actual risk: {result.scenario.expected.risk_level}/{result.actual.risk_level} · Expected/actual policy: {result.scenario.expected.policy_decision}/{result.actual.policy_decision}</p>
                  <p>Expected/actual incident: {String(result.scenario.expected.incident)}/{String(result.actual.incident)}</p>
                  <p>Expected signals: {result.scenario.expected.signals.join(", ") || "None"}</p>
                  <p>Actual signals: {result.actual.signals.join(", ") || "None"}</p>
                  <p>Missed: {result.signals.missed.join(", ") || "None"} · Unexpected: {result.signals.unexpected.join(", ") || "None"}</p>
                  {evaluation.include_ai && result.scenario.expected.intent && <p>AI expected/actual: {result.scenario.expected.intent}/{result.actual.intent ?? "Unavailable"} {result.actual.intent_confidence !== null && `(${Math.round(result.actual.intent_confidence * 100)}%)`}</p>}
                </details>
              ))}
            </div>
          </div>
        )}
      </section>
      <section className="intent-section" aria-labelledby="intent-heading">
        <div className="section-heading">
          <div>
            <h2 id="intent-heading">AI intent inference</h2>
            <p>Optional model interpretation of the deterministic evidence; not a statement of fact.</p>
          </div>
          <button disabled={isInferringIntent} onClick={() => void handleIntentAnalysis()}>Infer potential intent</button>
        </div>
        {intentAnalysis && (
          <div className="intent-result">
            <p className="intent-label">Most plausible intent</p>
            <h3>{intentAnalysis.intent_inference.intent.replaceAll("_", " ")}</h3>
            <p>Confidence: <strong>{Math.round(intentAnalysis.intent_inference.confidence * 100)}%</strong></p>
            <p>{intentAnalysis.intent_inference.summary}</p>
            <h4>Supporting evidence</h4>
            {intentAnalysis.intent_inference.evidence.length === 0 ? <p>No deterministic signals were cited.</p> : (
              <ul>
                {intentAnalysis.intent_inference.evidence.map((evidence) => (
                  <li key={evidence.signal}><strong>{evidence.signal}</strong> — {evidence.explanation}</li>
                ))}
              </ul>
            )}
            <h4>Uncertainties</h4>
            <ul>
              {intentAnalysis.intent_inference.uncertainties.map((uncertainty) => <li key={uncertainty}>{uncertainty}</li>)}
            </ul>
          </div>
        )}
      </section>
      <h2>Recent activities</h2>
      {error ? <p role="alert">{error}</p> : <ActivityTable activities={analysis?.recent_activities ?? activities} />}
    </main>
  );
}
