# Handover: Backend hosting decision

Paste this prompt into a fresh session to resume the backend hosting decision
for the Pharmacy Study App.

Last updated 2026-06-05.

---

**Task: help me complete and implement the backend hosting decision.**

The maintainer has chosen **Azure App Service** as the initial backend hosting
route, with **Azure Container Apps** reserved as a later revisit path after the
live demo is deployed. I may say "web service" informally; treat that as Azure
App Service unless I clarify otherwise.

**Important process context.**

This project is deliberate engineering practice, not autonomous implementation.
Before recommending or implementing anything:

1. Read `AGENTS.md`.
2. Read `docs/ai-collaboration.md`.
3. Read `docs/decisions.md`, especially:
   - #3 Database: PostgreSQL via Supabase.
   - #4 Auth: Supabase Auth, verified via JWKS.
   - #17 Environment modes.
   - #18 Alembic is the single source of truth.
   - #19 Frontend hosting: Azure Static Web Apps.
   - #20 Deployment readiness: health check and CORS.
4. Read `docs/plan.md`, especially task 18 Live demo deployment and task 19 CI.
5. Do a decision inventory before implementation.
6. `docs/decisions.md` #21 records the App Service-first backend hosting
   decision.
7. Do not add a Dockerfile, container registry, Azure workflow, or deployment
   config until the backend host decision entry is completed and an
   implementation plan is accepted.

**Current architecture.**

- Frontend: React/Vite SPA. Hosting decision is settled: Azure Static Web Apps.
- Backend: FastAPI + async SQLAlchemy + asyncpg.
- Database: Supabase Cloud Postgres. Do not move DB to Azure unless a new
  explicit decision is opened.
- Auth: Supabase Auth. Backend validates Supabase JWTs via JWKS.
- Migrations: Alembic only. Production apply path is `alembic upgrade head`.
- Health/CORS: task 13 is done. `/health` runs `SELECT 1`; `CORS_ORIGINS` is
  configured from backend environment.

**Goal.**

Help complete the App Service-first backend hosting decision and prepare the
smallest next deployment plan.

**Constraints.**

- Low-traffic portfolio/demo app.
- Use Azure because I have credits and want Azure practice.
- Keep Supabase Cloud for DB/Auth.
- Prefer a deployment path that is understandable and reproducible from GitHub.
- Avoid adding new cloud services unless they are necessary for the chosen path.
- Avoid hidden operational complexity I cannot explain.
- The backend must support these environment variables:
  `APP_ENV=production`, `AUTH_MODE=supabase`, `DATABASE_URL`, `SUPABASE_URL`,
  `SUPABASE_JWT_SECRET`, and `CORS_ORIGINS`.

**Questions to answer.**

1. What needs to be true before App Service deployment config is added?
2. What startup command should App Service use for this FastAPI app?
3. Which App Service pricing tier is acceptable for the initial demo?
4. Which environment variables must be configured in App Service app settings?
5. How should the manual deploy and verification runbook be written before
   GitHub Actions automation?
6. What exactly should trigger revisiting Container Apps/containerization?
7. How do we keep App Service-specific details out of application code?
8. What learning debt should the maintainer be ready to explain before merging?

**Expected output.**

1. Review the settled App Service-first decision in `docs/decisions.md` #21.
2. Review `docs/deploy.md` and prepare a small written plan for the first App
   Service setup slice.
3. Do not implement deployment config until the plan is accepted.

**Research expectations.**

Because Azure platform behavior changes, verify current facts using official
Microsoft Learn docs before making strong claims. Prefer primary sources for:

- App Service pricing/scaling/health checks/deployment.
- App Service Python/FastAPI startup command behavior.
- App Service app settings/environment variables/secrets.
- GitHub Actions integration for App Service, when automation is being planned.
- Container Apps only when documenting the future revisit trigger.

**Do not implement in this session unless I explicitly approve a plan.**

Likely implementation slices after the decision:

1. Review and refine `docs/deploy.md`.
2. Azure resource creation notes.
3. CI workflow for backend/frontend checks.
4. Backend deploy workflow.
5. Frontend `staticwebapp.config.json`.
6. Production migration and demo seed.
7. Future Dockerfile/Container Apps migration, only after an explicit revisit.
