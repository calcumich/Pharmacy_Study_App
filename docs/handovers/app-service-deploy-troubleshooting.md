# Handover: App Service deploy troubleshooting

Paste this prompt into a fresh session to resume the Azure App Service backend
deployment troubleshooting for the Pharmacy Study App.

Last updated 2026-06-06.

---

**Task: verify the accepted uv-based Azure App Service deployment fix.**

This is a learning-first project. The Oryx failure was analyzed deliberately.
The accepted fix is to standardize backend dependency management on uv and
commit `uv.lock`, which makes App Service/Oryx choose uv instead of Poetry.

## Required Reading

1. `AGENTS.md`
2. `docs/ai-collaboration.md`
3. `docs/decisions.md`, especially:
   - #3 Database: PostgreSQL via Supabase.
   - #4 Auth: Supabase Auth, verified via JWKS.
   - #17 Environment modes.
   - #18 Alembic is the single source of truth.
   - #19 Frontend hosting: Azure Static Web Apps.
   - #20 Deployment readiness: health check and CORS.
   - #21 Backend hosting: Azure App Service first.
4. `docs/deploy.md`
5. `.github/workflows/main_pharmacy-study-app.yml`
6. `pyproject.toml`
7. `alembic/env.py`

## Current Branch / Git State

The deploy planning work was done on branch `deploy/app-service-runbook`.
The Azure portal created the backend deploy workflow directly on `main`.
`main` was then rebased/merged into the deploy branch.

Important recent commits visible during the session:

- `2c33387 Add or update the Azure App Service build and deployment workflow config`
- `19aa935 Fix App Service workflow install step`
- `696a5ec Document App Service deployment plan`
- `b1864a8 update deploy docs`

Start with:

```bash
git status --short --branch
git log --oneline -5
```

Check whether `docs/deploy.md` has uncommitted handover/troubleshooting edits
from the prior session before making more changes.

## Current Cloud State

Azure:

- Resource group exists: `rg-pharmacy-study-demo`.
- Backend Azure App Service exists.
- Backend App Service URL from failed deploy logs:
  `https://pharmacy-study-app-cyeua7fzdwc3ecax.canadacentral-01.azurewebsites.net`
- Region: Canada Central.
- Runtime: Python 3.12.
- OS: Linux.
- Pricing tier: Free F1 / shared infrastructure.
- Startup command was set in the portal's stack settings:
  `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- App Service app settings have been configured with production Supabase values.
  Do not ask the maintainer to paste secret values.
- Deployment Center created a GitHub Actions workflow.
- The workflow uses Azure OIDC / user-assigned managed identity auth, not a
  publish profile secret.
- The frontend Azure Static Web Apps resource does not exist yet.

Supabase:

- Supabase Auth exists.
- Supabase Postgres now has app schema applied.
- The maintainer successfully ran:
  `alembic upgrade head`
- Alembic output showed:
  - `Running upgrade  -> 8d50f2cb30e1, create_core_schema`
  - `Running upgrade 8d50f2cb30e1 -> 3a3cda2329a1, add_user_study_tables`
  - `Running upgrade 3a3cda2329a1 -> f5ef1a0d7d64, seed_attribute_types`
- Supabase Table Editor confirmed the tables exist.
- `DATABASE_URL` uses the Supabase DB password and is secret.
- `SUPABASE_URL` is the project API URL and is not the DB connection string.

## Workflow State

Azure generated `.github/workflows/main_pharmacy-study-app.yml`.

The first generated workflow failed in the GitHub build job because it assumed:

```bash
pip install -r requirements.txt
```

but the repo has no `requirements.txt`; runtime dependencies live in
`pyproject.toml`.

That first failure was fixed in commit `19aa935` by changing the workflow's
local validation/install step to:

```bash
python -m pip install --upgrade pip
pip install -e .
```

That fix addressed the GitHub-side install failure. It did not address Azure
App Service's Oryx build behavior during deployment. The accepted follow-up fix
is to use uv:

```bash
uv sync --locked
```

## Resolved Failure To Verify

The latest backend deployment failed during Azure/Oryx build after the package
was sent to App Service.

Relevant log excerpt:

```text
[tool.poetry] section not found in /tmp/8dec3708f2f93c5/pyproject.toml
"2026-06-06 02:10:49"|WARNING|
[tool.poetry] section not found in /tmp/8dec3708f2f93c5/pyproject.toml | Exit code: 1
/bin/bash -c "oryx build /tmp/zipdeploy/extracted -o /home/site/wwwroot --platform python --platform-version 3.12 -p virtualenv_name=antenv --log-file /tmp/build-debug.log  -i /tmp/8dec3708f2f93c5 --compress-destination-dir | tee /tmp/oryx-build.log ; exit $PIPESTATUS "
Deployment Failed. Package deployment using ZIP Deploy failed.
```

Interpretation:

- GitHub Actions can install the project locally with `pip install -e .`.
- Deployment reaches Azure App Service.
- App Service/Oryx then runs its own build because Azure likely set
  `SCM_DO_BUILD_DURING_DEPLOYMENT=true`.
- Oryx sees `pyproject.toml` without `uv.lock`, takes the Poetry path, and
  fails because this project uses PEP 621/setuptools metadata, not
  `[tool.poetry]`.

The accepted fix is `pyproject.toml` plus committed `uv.lock`. Do not add
`requirements.txt` unless this uv path fails and a later decision accepts the
duplicate dependency list.

## Fix Chosen

- Standardize backend dependency management on uv.
- Keep `pyproject.toml` as the human-edited dependency source.
- Commit `uv.lock` for reproducible installs and App Service/Oryx detection.
- Keep App Service build automation enabled.
- Update GitHub Actions to validate with `uv sync --locked` and exclude
  `.venv/` from the deployment artifact.

## Recommended Next Session Order

1. Confirm current branch and uncommitted changes:
   `git status --short --branch`.
2. Read the files listed in Required Reading.
3. Inspect `.github/workflows/main_pharmacy-study-app.yml`.
4. Verify the App Service application setting
   `SCM_DO_BUILD_DURING_DEPLOYMENT` in Azure Portal if possible.
5. Confirm `uv.lock` is committed.
6. Confirm `.github/workflows/main_pharmacy-study-app.yml` uses
   `uv sync --locked`.
7. Push and rerun the GitHub Action.
8. If deployment succeeds, check:
    `https://pharmacy-study-app-cyeua7fzdwc3ecax.canadacentral-01.azurewebsites.net/health`

Expected `/health` response after a successful deploy and good DB config:

```json
{"status":"ok","db":"ok"}
```

## Things Not To Do Without Discussion

- Do not add `requirements.txt` unless the uv path fails and the duplicate
  dependency list is accepted as a follow-up tradeoff.
- Do not add Dockerfile, Azure Container Apps, or Azure Container Registry.
- Do not switch the project to Poetry just to satisfy Oryx.
- Do not move the database to Azure.
- Do not add Application Insights or Key Vault yet.
- Do not paste or commit `DATABASE_URL`, DB password, Supabase secret keys, or
  Azure credentials.
- Do not treat `/health` success as proof that app tables exist; migrations have
  already been applied, but this remains an important concept.

## Learning Checkout Questions

The maintainer should be able to answer before merging the deploy fix:

- What is Oryx, and why is it running after GitHub Actions already installed
  dependencies?
- What does `SCM_DO_BUILD_DURING_DEPLOYMENT` do for App Service?
- Why does this repo's `pyproject.toml` not contain `[tool.poetry]`?
- Why does committed `uv.lock` make Oryx use uv instead of Poetry?
- How should `uv.lock` be updated when `pyproject.toml` dependencies change?
- If we disable Oryx, what exactly is GitHub Actions responsible for packaging?
- Which parts of this fix are Azure deployment details versus app code changes?
