# TraceLoom

For Render, PostgreSQL, and Vercel setup, including the production environment-variable checklist and public-demo safeguards, see [DEPLOYMENT.md](DEPLOYMENT.md).

TraceLoom is a prototype behavioral security platform for recording controlled synthetic activity, deriving deterministic evidence, and optionally asking an LLM for a structured, advisory interpretation of that evidence. Synthetic subjects are test identities, not authenticated users or real employees. TraceLoom intentionally contains no authentication, agents, RAG, real interventions, or continuous monitoring.

## Current architecture

- **React + TypeScript + Vite** provides a routed security-operations UI at `http://localhost:5173`.
- **FastAPI** exposes a small JSON API at `http://localhost:8000`.
- **PostgreSQL** persists activities, running locally via Docker Compose.
- **SQLAlchemy** maps the `activities` table. The `metadata` column is PostgreSQL `JSONB` (with a portable JSON variant that keeps the unit tests fast).

The backend keeps routes, database models, and database operations separate. This is enough structure to keep later additions understandable without adding a framework of abstractions prematurely.

The frontend has purpose-specific pages for **Overview**, **Activity**, **Incidents**, **Policy & Response**, and **Evaluation**. They all use the same typed API layer; navigation does not create mock data or call the optional intent endpoint. The dashboard visually distinguishes observed telemetry, deterministic system output, and advisory AI inference.

## Activity simulator

The simulator creates coherent, chronological sequences with realistic metadata and inserts each sequence as a single database transaction. It is deterministic in structure—there is no AI inference—while timestamps are based on the current time and separated by realistic gaps.

Available scenario paths are:

- `normal-workday`: `LOGIN → REPOSITORY_ACCESS → FILE_ACCESS → API_REQUEST → LOGOUT`
- `large-data-access`: `LOGIN → REPOSITORY_ACCESS → five FILE_DOWNLOAD events → LOGOUT`
- `possible-data-exfiltration`: `LOGIN → REPOSITORY_ACCESS → five FILE_DOWNLOAD events → ARCHIVE_CREATED → EXTERNAL_UPLOAD`
- `credential-change`: `LOGIN → PASSWORD_CHANGE → LOGOUT`
- `baseline-history`: ten completed normal-workday sessions, intended to establish a useful historical baseline

The generic string `event_type` field supports these event categories and can grow without a schema migration: `LOGIN`, `LOGOUT`, `FILE_ACCESS`, `FILE_DOWNLOAD`, `FILE_UPLOAD`, `FILE_DELETE`, `REPOSITORY_ACCESS`, `REPOSITORY_CLONE`, `ARCHIVE_CREATED`, `EXTERNAL_UPLOAD`, `DATABASE_QUERY`, `API_REQUEST`, and `PASSWORD_CHANGE`.

## Behavioral baseline and deterministic analysis

A behavioral baseline is a summary of a user's completed historical sessions. Sessions are derived from `LOGIN` and `LOGOUT` events, so no new database table or identifier is needed. The baseline calculates average activities, downloads, uploads, repository accesses, database queries, download data volume, session duration, and common event types.

`GET /analysis/{user_id}` analyzes the latest session against earlier sessions when history exists. A first observed session is used to establish a baseline and returns low risk rather than being labeled anomalous merely because it is new.

The supported deterministic signals are:

- `HIGH_DOWNLOAD_VOLUME` — at least twice the average downloads per session, with a minimum of five downloads
- `LARGE_DATA_VOLUME` — at least twice the average downloaded data, with a minimum of 100 MB
- `ARCHIVE_AFTER_DOWNLOADS` — archive creation within 30 minutes of at least three downloads
- `EXTERNAL_UPLOAD_AFTER_DOWNLOADS` — external upload within 30 minutes of at least three downloads
- `UNUSUAL_EVENT_SEQUENCE` — three or more downloads followed by archive creation and external upload
- `OFF_PATTERN_ACTIVITY` — event types absent from the historical baseline

Risk is a transparent, deterministic summary of the detected signals—not an AI prediction or a claim that a user is malicious. The rules live in `backend/app/services/risk_service.py` and are intentionally easy to change:

| Signal severity | Points |
| --- | ---: |
| High | 3 |
| Medium | 2 |
| Low | 1 |

| Total points | Risk level |
| --- | --- |
| 0–2 | Low |
| 3–5 | Medium |
| 6+ | High |

```text
React dashboard
  → FastAPI routes
    → simulator service → activity service → PostgreSQL
    → analysis service → baseline + anomaly + risk services → JSON result
```

This deterministic layer provides clear evidence and measurable signals for the optional intent engine described below. It deliberately does not include embeddings, RAG, agents, authentication, or live endpoint monitoring.

## Intent inference

Intent inference is an optional, explicitly requested layer on top of deterministic analysis. `GET /intent/{user_id}` first performs the same baseline, anomaly, and risk analysis as `GET /analysis/{user_id}`. Only then does it send a minimal structured evidence object to the OpenAI API and return a potential interpretation.

```text
Activity
  ↓
Behavioral Baseline
  ↓
Anomaly Detection
  ↓
Risk Scoring
  ↓
Intent Inference
  ↓
Structured Security Explanation
  ↓
Dashboard
```

The LLM receives only this structure—no environment variables, credentials, or database connection details:

```json
{
  "user_id": "investigation-user",
  "deterministic_risk": {"risk_level": "high", "risk_score": 9},
  "behavioral_baseline": {"average_file_downloads": 1.0},
  "deterministic_signals": [{"type": "HIGH_DOWNLOAD_VOLUME", "severity": "high", "evidence": {}}],
  "recent_activity_sequence": [{"timestamp": "...", "event_type": "FILE_DOWNLOAD", "metadata": {}}]
}
```

The structured model result is:

```json
{
  "intent": "DATA_EXFILTRATION",
  "confidence": 0.87,
  "summary": "Potential intent based on the supplied telemetry.",
  "evidence": [{"signal": "HIGH_DOWNLOAD_VOLUME", "explanation": "..."}],
  "uncertainties": ["Authorization context is unavailable."]
}
```

`intent` is limited to `NORMAL_WORK`, `BULK_DATA_ACCESS`, `DATA_EXFILTRATION`, `CREDENTIAL_MODIFICATION`, `REPOSITORY_ACTIVITY`, `AUTOMATED_ACTIVITY`, or `UNKNOWN`. The service rejects confidence values outside `0–1` and rejects model evidence that cites a signal not already supplied by deterministic analysis.

The system prompt is stored separately in `backend/app/prompts/intent_system_prompt.py`. It treats activity metadata as untrusted telemetry, never system instructions. Telemetry is sent in a separately labeled user message, and the prompt prohibits inventing events, users, files, destinations, policies, or evidence. This is prompt-injection mitigation, not a substitute for production security controls.

Configure the backend only (never `VITE_` frontend variables) before running the intent endpoint:

```bash
cp .env.example .env  # Only if .env does not already exist.
# Add OPENAI_API_KEY=... to .env locally. Never commit or share this file.
# OPENAI_MODEL=gpt-6-astra is optional; this is the default.
```

The backend automatically loads `intentshield/.env`; shell-exported variables still take precedence.

Install dependencies after pulling this milestone:

```bash
cd backend
pip install -r requirements.txt
```

Then explicitly request an inference:

```bash
curl 'http://localhost:8000/intent/investigation-user'
```

The dashboard never calls this endpoint during refreshes. Use **Infer potential intent** in the separate **AI intent inference** section. The deterministic analysis section remains visible independently.

The test suite mocks the OpenAI client, so tests make no network calls and do not need a real API key.

## Incident investigation and evidence graph

TraceLoom can project a high-risk latest session into a dynamic incident investigation. Incidents are derived at request time from existing controlled telemetry; this milestone adds no incident database table and does not duplicate activity records.

```text
Telemetry
  ↓
Behavioral Baseline
  ↓
Deterministic Detection
  ↓
Risk
  ↓
Incident
  ↓
Evidence Graph / Timeline
  ↓
Optional AI Intent
```

`GET /incidents/{user_id}` runs the existing deterministic analysis and creates an incident only when the latest session has **high** deterministic risk. Low- and medium-risk responses return `"incident": null`. This endpoint never calls OpenAI, so the investigation workflow works without API credits.

The response contains:

- The incident summary with activity IDs and deterministic signal types
- A chronological timeline of real activity records and rule-generated transition explanations
- The deterministic signals that support the incident
- An in-memory evidence graph using `USER`, `ACTIVITY`, `SIGNAL`, and `INCIDENT` nodes
- `intent: null` unless a future persistence layer makes a previously generated AI inference available

Evidence integrity is deliberate: every activity graph node contains a real activity ID, every signal node comes from deterministic analysis, and activity-to-signal edges use the same event/time predicates as anomaly detection. AI evidence is neither requested nor included as deterministic evidence.

Demonstrate the full investigation flow without OpenAI:

```bash
curl -X POST 'http://localhost:8000/simulate/baseline-history?user_id=investigation-user'
curl -X POST 'http://localhost:8000/simulate/possible-data-exfiltration?user_id=investigation-user'
curl 'http://localhost:8000/analysis/investigation-user'
curl 'http://localhost:8000/incidents/investigation-user'
```

## Deterministic policy and dry-run response

The policy engine converts existing deterministic risk and anomaly signals into explainable **recommendations**, never real interventions. AI intent remains advisory analyst context and does not participate in policy selection.

```text
Telemetry
  ↓
Behavioral Baseline
  ↓
Deterministic Detection
  ↓
Risk
  ↓
Incident
  ↓
Evidence Graph
  ↓
Optional AI Intent
  ↓
Policy Engine
  ↓
Intervention Recommendation
```

`GET /policy/{user_id}` uses the existing deterministic analysis and applies readable rules:

- Low risk → `ALLOW`
- Medium risk → `MONITOR`
- High download volume → `MONITOR`
- High download volume plus large data volume → `TEMPORARILY_RESTRICT_DOWNLOADS`
- External upload after downloads → `RESTRICT_EXTERNAL_UPLOAD`
- Unusual download/archive/upload sequence → `REQUIRE_REAUTHENTICATION`
- An off-pattern password-change event in a high-risk session → `REQUIRE_MFA`
- Two or more high-severity signals → `ESCALATE_TO_SECURITY`

Overall policy posture uses fixed precedence: `ESCALATE > RESTRICT > CHALLENGE > MONITOR > ALLOW`. Every recommendation includes only deterministic signal identifiers that triggered it.

`POST /policy/{user_id}/simulate` records a dry run, never sends a command, changes an account, blocks traffic, or invokes an external security system. It accepts a currently recommended action and returns `mode: "DRY_RUN"` and `executed: false`. The PostgreSQL-backed audit history is available at `GET /policy/{user_id}/audit`.

Try the policy flow with no OpenAI call:

```bash
curl 'http://localhost:8000/policy/investigation-user'
curl -X POST 'http://localhost:8000/policy/investigation-user/simulate' \
  -H 'Content-Type: application/json' \
  -d '{"action":"RESTRICT_EXTERNAL_UPLOAD"}'
curl 'http://localhost:8000/policy/investigation-user/audit'
```

## Security evaluation harness

The evaluation harness measures the current deterministic system against a fixed, synthetic dataset. It does **not** claim real-world or production security effectiveness. Its purpose is to make the system's current detection, signal, and policy limitations visible.

The dataset contains 20 explicitly labeled scenarios: 10 benign and 10 suspicious. Ground truth is defined separately from the telemetry builders and includes expected risk, incident status, signals, policy decision, and optional intent. It is never generated by an LLM.

Run the default, no-cost deterministic evaluation:

```bash
curl -X POST 'http://localhost:8000/evaluation/run' \
  -H 'Content-Type: application/json' \
  -d '{"include_ai":false}'
```

Inspect the fixed ground-truth definitions:

```bash
curl 'http://localhost:8000/evaluation/scenarios'
```

The report includes incident confusion-matrix counts, precision, recall, F1, accuracy, policy accuracy, signal matches/misses/unexpected signals, and every per-scenario expected-versus-actual result.

AI intent evaluation is optional and disabled by default. Enable it only when intentionally evaluating scenarios that carry an expected intent label:

```bash
curl -X POST 'http://localhost:8000/evaluation/run' \
  -H 'Content-Type: application/json' \
  -d '{"include_ai":true}'
```

That mode can make live model requests and incur API usage costs. Automated tests mock the intent service; ordinary evaluation and all default API calls make zero OpenAI requests.

Synthetic scenarios deliberately reveal current limitations. For example, benign first-time download, archive, and standalone-upload patterns may receive an unexpected low-severity `OFF_PATTERN_ACTIVITY` signal, while isolated unusual credential and repository-clone patterns remain below the current risk threshold. These are reported as evaluation mismatches rather than hidden by changing thresholds or labels.

## Prerequisites

- Docker Desktop (or Docker Engine with Compose)
- Python 3.11+ and `pip`
- Node.js 20+ and npm

## Start the project

From this directory, create a local environment file and start PostgreSQL:

```bash
cp .env.example .env
docker compose up -d postgres
```

In a second terminal, create and activate a Python virtual environment, install backend dependencies, and run FastAPI:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a; source ../.env; set +a
uvicorn app.main:app --reload
```

In a third terminal, install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dashboard checks `/health` and loads the recent activity table from `/activities`.

## API

`GET /health` returns:

```json
{"status":"ok"}
```

`POST /activities` accepts an activity:

```bash
curl -X POST http://localhost:8000/activities \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"student-123","event_type":"file_download","metadata":{"file_name":"notes.pdf"}}'
```

`GET /activities` returns up to 100 activities, newest first.

Filter activity history to one user with:

```bash
curl 'http://localhost:8000/activities?user_id=simulated-user'
```

Generate a scenario with the simulator:

```bash
curl -X POST 'http://localhost:8000/simulate/possible-data-exfiltration?user_id=demo-user'
```

Try each scenario manually by replacing the last path segment with `normal-workday`, `large-data-access`, `possible-data-exfiltration`, or `credential-change`. The React dashboard provides the same actions through its **Simulate scenario** buttons.

To produce a realistic analysis demonstration, establish normal history and then generate a possibly risky pattern for the same user:

```bash
curl -X POST 'http://localhost:8000/simulate/baseline-history?user_id=investigation-user'
curl -X POST 'http://localhost:8000/simulate/possible-data-exfiltration?user_id=investigation-user'
curl 'http://localhost:8000/analysis/investigation-user'
```

For a normal analysis demonstration, generate baseline history followed by a normal workday, then request `/analysis/normal-user`.

## Run backend tests

After activating the backend virtual environment:

```bash
cd backend
pytest
```

The tests use an in-memory SQLite database only to isolate tests from local PostgreSQL. They cover simulator scenarios, baseline calculation, every anomaly signal, scoring levels, analysis results, generated timestamp ordering, invalid scenario names, and user filtering. Production and development application configuration use the `DATABASE_URL` environment variable; Docker PostgreSQL is configured from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.

## Data flow

The dashboard calls the small client functions in `frontend/src/api`, which issue HTTP requests to FastAPI. For simulations, the simulator service first creates activity payloads; the activity service then stores them through SQLAlchemy. PostgreSQL returns the stored activity data, then FastAPI serializes it as JSON for React to render.
