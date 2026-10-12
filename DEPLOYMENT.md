# TraceLoom deployment guide

This guide prepares a **public synthetic-telemetry demonstration**, not a production enterprise-security deployment. Do not place real employee, customer, or production security data in this system.

## Architecture

```text
Vercel (React/Vite SPA)
  -- VITE_API_BASE_URL --> Render (FastAPI)
                                  --> Render PostgreSQL
                                  --> OpenAI API (optional, server-side only)
```

Vercel only receives public build-time settings. Render holds the database URL, OpenAI key, CORS allow-list, and access token.

## Render backend

Create a Render Web Service from this repository and use `render.yaml`, or set the service root directory to `backend` manually.

| Setting | Value |
| --- | --- |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` |
| Health check path | `/health` |
| Runtime | Python 3.11 |

Set these Render environment variables. The values shown here are names only; never commit actual values.

| Variable | Required | Notes |
| --- | --- | --- |
| `TRACELOOM_ENV` | Yes | Set to `production`. |
| `DATABASE_URL` | Yes | Render PostgreSQL internal URL preferred. `postgres://` and `postgresql://` are converted safely to SQLAlchemy's psycopg format. Include provider-required SSL settings when using an external database. |
| `CORS_ORIGINS` | Yes | Comma-separated explicit frontend origins, such as the production Vercel URL and any preview URL intentionally supported. Never use `*` in production. |
| `OPENAI_API_KEY` | Optional | Keep only on Render. Omit it to disable model inference. |
| `OPENAI_MODEL` | Optional | Defaults to `gpt-6-astra`; set only to a model compatible with the existing structured-output call. |
| `INTENT_ACCESS_TOKEN` | Required when `OPENAI_API_KEY` is set | A long random operator-only secret. It is never added to Vercel or frontend code. |
| `INTENT_RATE_LIMIT_REQUESTS` | Recommended | Default `3`, per client IP per hour for paid inference. |
| `INTENT_RATE_LIMIT_WINDOW_SECONDS` | Recommended | Default `3600`. |
| `WRITE_RATE_LIMIT_REQUESTS` | Recommended | Default `30`, per client IP per hour for simulator, dry-run, and evaluation writes. |
| `WRITE_RATE_LIMIT_WINDOW_SECONDS` | Recommended | Default `3600`. |

The application refuses to start in production without `DATABASE_URL`, explicit `CORS_ORIGINS`, or (when OpenAI is configured) `INTENT_ACCESS_TOKEN`.

### Database setup

1. Create a managed PostgreSQL database in Render, or another PostgreSQL-compatible provider.
2. Copy its private/internal connection URL into Render as `DATABASE_URL`; do not put it in Vercel.
3. Ensure the database is reachable from the Render web service. Prefer the same Render region and private network.
4. On startup, TraceLoom creates its current tables with SQLAlchemy. This is suitable for the prototype; use migration tooling before schema changes in a long-lived deployment.
5. Back up or periodically reset the demo database. Simulator events and dry-run audit records persist.

## Vercel frontend

Import the same repository into Vercel with **Root Directory** set to `frontend`.

| Setting | Value |
| --- | --- |
| Framework | Vite |
| Build command | `npm run build` |
| Output directory | `dist` |
| SPA refresh support | `vercel.json` rewrites all routes to `index.html` |

Set Vercel environment variables for each intended environment:

| Variable | Public? | Value |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Yes | The HTTPS Render backend URL, without a trailing slash. |
| `VITE_ENABLE_INTENT_INFERENCE` | Yes | Set `false` for a public demo. |

All `VITE_*` variables are embedded in the browser build. Never use them for API keys, database URLs, Render tokens, or `INTENT_ACCESS_TOKEN`.

After Vercel creates the production URL, add that exact origin to Render's `CORS_ORIGINS` and redeploy the backend. Add preview origins only if previews are intentionally supported.

## Paid OpenAI endpoint protection

`GET /intent/{user_id}` and `POST /evaluation/run` with `{"include_ai": true}` are protected server-side in production:

1. They require `X-TraceLoom-Intent-Token` matching Render's `INTENT_ACCESS_TOKEN` before the application calls OpenAI.
2. They are rate-limited per proxy-resolved client IP by an in-process sliding window.
3. The public Vercel demo sets `VITE_ENABLE_INTENT_INFERENCE=false`, so its UI does not offer the paid action.

This intentionally trades public self-service AI inference for cost control. A developer/operator can use the protected endpoint from a secure server-to-server tool with the header; do not put this token in a browser, Vercel variable, or public client application.

The built-in limiter is enforceable for one Render service instance. If you scale to multiple instances or need a shared, durable quota, move the counters to Redis or a managed API gateway before enabling AI access for additional trusted users. Authentication with per-user authorization and a durable quota store is the appropriate next step for a non-demo product.

## Public demo safeguards

The activity-ingestion, synthetic simulator, evaluation-run, and dry-run policy endpoints change database state or consume compute. Production applies a server-side per-IP write limit to these routes. For a public demo, also consider:

- Keep the database synthetic and use a scheduled reset/snapshot restore.
- Do not grant database credentials to Vercel or users.
- Keep AI disabled in the public UI; the deterministic guided demo remains fully functional.
- Use a single Render instance unless replacing the in-process limits with a shared store.
- Add authentication, CAPTCHA, or an API gateway before allowing broad write access or paid inference.
- Monitor Render/OpenAI usage and set provider-side spend or usage alerts outside this repository.

## Pre-deployment checklist

- [ ] `npm run build` succeeds from `frontend`.
- [ ] `.venv/bin/python -m pytest -q` succeeds from `backend`.
- [ ] `.env` is ignored and no real secret is committed.
- [ ] Render has `DATABASE_URL`, `CORS_ORIGINS`, and production environment values.
- [ ] Vercel has only the public `VITE_*` values listed above.
- [ ] Vercel URL is present in Render `CORS_ORIGINS`.
- [ ] `/health` responds from Render before pointing Vercel at it.

No resource is created by these files; deployment remains a manual step.
