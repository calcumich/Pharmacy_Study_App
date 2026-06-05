# Handover: Azure deployment

Paste this prompt into a fresh session to resume the Azure deployment thread.
Last updated 2026-06-05.

---

**Task: resume Azure deployment planning for the Pharmacy Study App.**

**Important process context.**

This project is being run as AI-assisted deliberate practice, not autonomous
agent implementation. Before making non-trivial deployment changes:

1. Read `AGENTS.md`.
2. Read `docs/ai-collaboration.md`.
3. Do a decision inventory before implementation.
4. Agents may prepare decision worksheets with options and questions, but the
   human maintainer owns final decision text, current understanding, and
   learning debt.
5. Do not mix separate `docs/adr/*.md` files with `docs/decisions.md` unless
   the maintainer first makes an explicit process decision to migrate decision
   storage.

Decision storage is still `docs/decisions.md`. Do not create separate ADR files
unless the maintainer first makes an explicit process decision to migrate
decision storage.

**Where the app architecture stands.**

The app is feature-complete enough to start deployment plumbing. Auth
(Supabase JWKS) and migrations (pure Alembic, decision #18) are done. The target
cloud is Azure because the maintainer has dev credits and wants Azure practice.

- **DB + Auth:** Supabase Cloud stays. Do not move to Azure Postgres unless the
  maintainer opens a new decision.
- **Frontend:** Azure Static Web Apps is settled in decision #19.
- **Backend:** Azure App Service is the initial backend hosting direction. The
  maintainer wants to get the live demo deployed first, then revisit Azure
  Container Apps/containerization later if the added complexity is useful.
  `docs/decisions.md` #21 records the decision.
- **Deployment:** intended direction is GitHub Actions driving frontend and
  backend deploys.

**Hard blockers for public Azure deploy.**

1. **App Service deploy runbook needs review.**
   - `docs/deploy.md` now documents the App Service startup command, required
     app settings, and manual verification steps.
   - Review and refine the runbook before creating Azure resources or adding
     GitHub Actions automation.
2. **Frontend environment wiring.**
   - `frontend/src/api/client.ts` already reads `VITE_API_BASE_URL`; the Azure
     Static Web Apps build/deploy path must set it.
   - Also set `VITE_SUPABASE_URL`, `VITE_PUBLISHABLE_KEY`,
     `VITE_AUTH_MODE=supabase`, and `VITE_USE_MOCK=false` for the real demo.

**Nice-to-have before sharing the URL broadly.**

- Task 17: seeded demo dataset. Otherwise the real deployed app may feel empty.
- Task 19: CI on PRs.
- Error reporting: open vendor choice. Application Insights is the Azure-native
  option; Sentry is the stronger developer-experience option; doing nothing for
  the first locked-down demo is also viable.

**Open decisions / worksheets to prepare.**

1. **Decision storage process.**
   - Current canonical store is `docs/decisions.md`.
   - If the maintainer wants per-decision ADR files, first create a process
     decision defining the directory, template, numbering, and whether
     `docs/decisions.md` is frozen, migrated, or becomes an index.
2. **Frontend/backend access strategy.**
   - CORS is implemented with `CORS_ORIGINS`, but the deployed Azure Static Web
     Apps origin still needs to be added to backend app settings.
   - Decide whether pull-request preview frontend URLs should call the deployed
     backend or remain in mock mode.
4. **Lockdown strategy.**
   - Supabase app auth only vs. Azure Static Web Apps password protection vs.
     SWA auth routes vs. backend ingress restrictions.
5. **Error reporting.**
   - Application Insights vs. Sentry vs. defer.

**Suggested fresh-session order.**

1. Run `git status --short` and inspect current uncommitted docs changes.
2. Read `AGENTS.md`, `docs/ai-collaboration.md`, `docs/decisions.md`, and
   `docs/plan.md`.
3. Review `docs/deploy.md` and prepare a small App Service deployment plan:
   - App Service resource shape and pricing tier to use for the demo.
   - Python runtime and startup command for `app.main:app`.
   - Required backend app settings:
     `APP_ENV=production`, `AUTH_MODE=supabase`, `DATABASE_URL`,
     `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, and `CORS_ORIGINS`.
   - Manual verification path: `/health`, authenticated API call, and frontend
     CORS check from Azure Static Web Apps.
4. Implement only the accepted deployment-docs slice first, then consider
   GitHub Actions automation.
5. Stop and do the learning checkout before moving to Dockerfile,
   Container Apps, or extra Azure services.

**Environment reminders.**

- Production/staging backend must use `APP_ENV=production|staging` and
  `AUTH_MODE=supabase`.
- `AUTH_MODE=dev` is guarded so it should only work with `APP_ENV=local`.
- `DATABASE_URL` must use `postgresql+asyncpg://`.
- Supabase Cloud remains the canonical production database and auth provider.
- The frontend can deploy in mock mode with `VITE_USE_MOCK=true` as a fallback,
  but the real demo path should use `VITE_USE_MOCK=false`.
- Alembic is the only migration path: run `alembic upgrade head`; do not
  recreate deleted SQL migration files.

**Out of scope for the first fresh-session slice.**

- Dockerfile / container registry / Container Apps.
- GitHub Actions deployment workflows.
- Azure resource creation.
- Demo seed data.
- README screenshots.
- Search endpoint, session-close endpoint, FSRS weights, and ingestion pipeline.
