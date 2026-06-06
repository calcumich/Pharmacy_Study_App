# Azure Deployment Runbook

This runbook describes the first cloud deployment path for the Pharmacy Study
App. It is intentionally manual-first: prove the deployment path, then automate
it with GitHub Actions after the steps are understood.

## Current Target

- Frontend: Azure Static Web Apps.
- Backend: Azure App Service running the FastAPI app.
- Database: Supabase Cloud Postgres.
- Auth: Supabase Auth, verified by the backend via JWKS.
- Migrations: Alembic only, applied with `alembic upgrade head`.

Azure App Service is the initial backend host per decision #21. Do not add a
Dockerfile, container registry, Azure Container Apps resource, Azure Postgres,
Key Vault, or Application Insights unless a later decision or plan explicitly
accepts that work.

## Portability Boundary

Azure is the current deployment platform, not an application dependency. Keep
Azure-specific assumptions out of Python and TypeScript application code.

Portable app contract:

- Backend ASGI app: `app.main:app`.
- Backend configuration: environment variables.
- Backend database URL: standard `postgresql+asyncpg://...` SQLAlchemy URL.
- Backend migration command: `alembic upgrade head`.
- Backend health endpoint: `GET /health`.
- Frontend backend URL: `VITE_API_BASE_URL` at build time.

Azure-specific details belong in this runbook, Azure resource configuration, or
future GitHub Actions workflow files.

## Values To Collect

Create these values before configuring Azure.

Backend:

- Azure resource group name.
- App Service app name.
- App Service plan name, region, OS, Python version, and pricing tier.
- App Service backend URL, for example
  `https://<backend-app-name>.azurewebsites.net`.
- Supabase Postgres async URL for `DATABASE_URL`.
- Supabase project URL for `SUPABASE_URL`.
- Supabase JWT secret for `SUPABASE_JWT_SECRET` if the project still requires
  the legacy HS256 fallback. Modern JWKS verification primarily depends on
  `SUPABASE_URL`.
- Azure Static Web Apps production origin for `CORS_ORIGINS`.

Frontend:

- Static Web App name.
- Static Web App production URL.
- Backend API base URL for `VITE_API_BASE_URL`.
- Supabase project URL for `VITE_SUPABASE_URL`.
- Supabase publishable/anon key for `VITE_PUBLISHABLE_KEY`.

## Resource Creation Checklist

Fill this in before creating Azure resources. Keep names boring and predictable;
the goal is to make the deployment easy to explain and reproduce.

Project scope:

- Azure subscription:
- Resource group name:
- Region:
- Owner:
- Purpose: portfolio/demo deployment

Backend App Service:

- App Service app name:
- App Service plan name:
- Runtime stack: Python
- Python version:
- OS: Linux
- Pricing tier:
- Backend URL:
- Startup command:
  `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

Backend app settings:

- `APP_ENV=production`
- `AUTH_MODE=supabase`
- `DATABASE_URL=<supabase-postgres-asyncpg-url>`
- `SUPABASE_URL=<supabase-project-url>`
- `SUPABASE_JWT_SECRET=<legacy-jwt-secret-or-empty-if-not-needed>`
- `CORS_ORIGINS=<azure-static-web-app-origin>`

Frontend Static Web Apps:

- Static Web App name:
- Region:
- Deployment branch:
- App location: `frontend`
- API location: empty / none
- Output location: `dist`
- Frontend URL:

Frontend build settings:

- `VITE_USE_MOCK=false`
- `VITE_AUTH_MODE=supabase`
- `VITE_API_BASE_URL=<backend-url>`
- `VITE_SUPABASE_URL=<supabase-project-url>`
- `VITE_PUBLISHABLE_KEY=<supabase-publishable-or-anon-key>`

Supabase:

- Project URL:
- Postgres connection mode used for `DATABASE_URL`:
- JWT verification mode: JWKS via `SUPABASE_URL`
- Demo user/account plan:

## Supabase Database Preparation

Supabase Auth and Supabase Postgres are separate pieces of this deployment.
Having Supabase Auth configured does not mean the app database schema exists.
Before the Azure backend can serve real API routes, Alembic migrations must be
applied to Supabase Postgres.

Use the Supabase dashboard connection string as the starting point for
`DATABASE_URL`:

1. In Supabase, open the project.
2. Click **Connect**.
3. Copy the **Session pooler** or **Transaction pooler** URI.
4. Replace the password placeholder with the database password.
5. Change only the URI scheme from `postgres://` or `postgresql://` to
   `postgresql+asyncpg://`.

Example transformation:

```text
postgres://postgres.<project-ref>:[YOUR-PASSWORD]@...pooler.supabase.com:5432/postgres
```

becomes:

```text
postgresql+asyncpg://postgres.<project-ref>:<database-password>@...pooler.supabase.com:5432/postgres
```

Keep the host, port, username, project ref, and database path exactly as
Supabase provides them. The `+asyncpg` part is for SQLAlchemy's async driver;
Supabase will not show that form in the dashboard.

`DATABASE_URL` is a secret because it includes the database password. Do not
commit the real value to docs, source code, or GitHub Actions workflow files.

To apply migrations from a local shell, set the backend environment to use the
Supabase Cloud database:

```text
APP_ENV=local
AUTH_MODE=supabase
DATABASE_URL=<supabase-postgres-asyncpg-url>
SUPABASE_URL=<supabase-project-url>
SUPABASE_JWT_SECRET=
CORS_ORIGINS=http://localhost:5173
```

Then run:

```bash
alembic upgrade head
```

After the command succeeds, verify Supabase contains the app schema:

- `alembic_version`
- `drug_classes`
- `drugs`
- `attribute_types`
- `study_sessions`
- `review_events`
- `srs_state`
- `flashcard_state`

`/health` only proves the backend can run `SELECT 1`; it does not prove the app
tables exist. Check the migrated tables before treating the cloud database as
deployment-ready.

Resource guardrails:

- Do not create Azure Postgres.
- Do not create Azure Container Registry.
- Do not create Azure Container Apps.
- Do not add Key Vault or Application Insights for the first deploy.
- Do not hard-code Azure resource names or URLs into application code.
- Record any portal-only choice in this runbook before relying on it.

## Backend App Service Setup

Use the lowest-cost/free practical App Service tier for the first demo while
using Azure credits. Revisit the tier if the demo needs features or reliability
that the selected tier does not provide.

Create an Azure App Service resource for the backend with:

- Runtime stack: Python.
- Python version: compatible with the repo's `requires-python = ">=3.12"`.
- OS: Linux.
- Deployment source: manual/local first; GitHub Actions later.

Configure the App Service startup command:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This matches the repo's current runtime dependencies. A Gunicorn +
`uvicorn.workers.UvicornWorker` command may be a later production-hardening
option, but it requires adding `gunicorn` as a backend dependency first.

## Backend App Settings

Configure these App Service app settings. Azure App Service exposes app settings
as environment variables to the running app and restarts the app when settings
change.

```text
APP_ENV=production
AUTH_MODE=supabase
DATABASE_URL=<supabase-postgres-asyncpg-url>
SUPABASE_URL=<supabase-project-url>
SUPABASE_JWT_SECRET=<legacy-jwt-secret-or-empty-if-not-needed>
CORS_ORIGINS=<azure-static-web-app-origin>
```

Do not set `AUTH_MODE=dev` in Azure. The backend rejects dev auth when
`APP_ENV` is not `local`.

`CORS_ORIGINS` should include the deployed Azure Static Web Apps origin once it
exists. Keep it explicit. Do not use a wildcard for the authenticated API unless
a later decision accepts that risk.

## Backend Deploy And Migration

Manual-first backend deploy:

1. Deploy the backend source to App Service.
2. Confirm App Service installs the Python dependencies from `pyproject.toml`.
3. Confirm the startup command is configured.
4. Confirm all backend app settings are present.
5. Run `alembic upgrade head` against the Supabase production database.
6. Open the backend URL and check `GET /health`.

Do not run migrations blindly against production. Confirm `DATABASE_URL` points
to the intended Supabase project before running Alembic.

Expected backend verification:

```text
GET https://<backend-app-name>.azurewebsites.net/health
```

Expected response when Supabase Postgres is reachable:

```json
{"status":"ok","db":"ok"}
```

If `/health` returns 503, check the App Service logs, `DATABASE_URL`, Supabase
network/access settings, and whether migrations have been applied.

## Frontend Static Web Apps Setup

Create the Azure Static Web Apps frontend resource after the backend URL is
known, or be ready to update frontend build settings once the backend URL
exists.

Frontend build settings for the real demo:

```text
VITE_USE_MOCK=false
VITE_AUTH_MODE=supabase
VITE_API_BASE_URL=https://<backend-app-name>.azurewebsites.net
VITE_SUPABASE_URL=<supabase-project-url>
VITE_PUBLISHABLE_KEY=<supabase-publishable-or-anon-key>
```

The frontend reads Vite environment variables at build time. If these values
change, rebuild and redeploy the Static Web App.

Mock-mode fallback:

```text
VITE_USE_MOCK=true
```

Mock mode can keep a demo shell online even if the backend is unavailable, but
the real deployment path should use `VITE_USE_MOCK=false`.

## End-To-End Verification

After backend and frontend are both deployed:

1. Visit the Static Web Apps URL.
2. Confirm the frontend loads without local `localhost` API calls.
3. Sign in through Supabase Auth.
4. Confirm authenticated API requests include a bearer token.
5. Confirm the browser can read backend responses from the SWA origin.
6. Confirm class/drug browsing works against the real backend.
7. Confirm a flashcard review can be submitted and returns a new due date.
8. Check App Service logs for startup, database, auth, or CORS errors.

Common failure modes:

- Frontend calls `http://localhost:8000`: `VITE_API_BASE_URL` was not set during
  the SWA build.
- Browser reports CORS failure: backend `CORS_ORIGINS` does not include the SWA
  origin exactly.
- Backend returns 401: Supabase session token is missing, expired, or cannot be
  verified from the configured `SUPABASE_URL`.
- `/health` returns 503: backend cannot reach Supabase Postgres.
- App Service starts but API routes fail: check startup command, dependency
  install, app settings, and logs.

## Automation Follow-Up

Only automate after the manual path is understood.

Likely next automation slices:

1. CI workflow: backend tests and frontend build on pull requests.
2. Backend deploy workflow to Azure App Service.
3. Frontend deploy workflow to Azure Static Web Apps.
4. Document how production migrations are triggered and who is allowed to run
   them.

Do not hide migrations inside an opaque deploy step until the production
migration path is clear.

## Revisit Container Apps

Revisit Azure Container Apps when one of the decision #21 triggers appears:

- App Service billing becomes annoying.
- Scale-to-zero matters.
- A required feature is easier in Container Apps.
- Docker/container deployment becomes the next learning goal.
- Running the same backend image across multiple platforms becomes useful.

Until then, do not add a Dockerfile or container registry just for the first
App Service deployment.

## References

- Azure App Service app settings are exposed as environment variables and are
  encrypted at rest:
  <https://learn.microsoft.com/en-us/azure/app-service/configure-common>
- Azure App Service Python configuration and startup command behavior:
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-python>
- Azure App Service FastAPI quickstart:
  <https://learn.microsoft.com/en-us/azure/app-service/quickstart-python>
- Azure Static Web Apps configuration:
  <https://learn.microsoft.com/en-us/azure/static-web-apps/configuration>
