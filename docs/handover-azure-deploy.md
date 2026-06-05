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

There was process churn in the previous session. `docs/decisions.md` may contain
an incomplete `## 20. DB-backed health check and configurable CORS` stub near the
bottom. If present, treat it as a placeholder for the maintainer, not an accepted
agent-authored decision. Do not fill it in unless the maintainer explicitly asks
for that. Prefer preparing a worksheet/options summary for the maintainer.

**Where the app architecture stands.**

The app is feature-complete enough to start deployment plumbing. Auth
(Supabase JWKS) and migrations (pure Alembic, decision #18) are done. The target
cloud is Azure because the maintainer has dev credits and wants Azure practice.

- **DB + Auth:** Supabase Cloud stays. Do not move to Azure Postgres unless the
  maintainer opens a new decision.
- **Frontend:** Azure Static Web Apps is settled in decision #19.
- **Backend:** Azure Container Apps vs. Azure App Service is still open.
  Recommendation from prior work was Container Apps for container-native deploy
  and scale-to-zero, but the maintainer should own the final decision.
- **Deployment:** intended direction is GitHub Actions driving frontend and
  backend deploys.

**Hard blockers for public Azure deploy.**

1. **Task 13 in `docs/plan.md`: configurable CORS + real `/health`.**
   - Current `/health` is static and does not exercise the DB.
   - CORS must allow the deployed Azure Static Web Apps origin.
   - This is the first implementation slice.
2. **No backend `Dockerfile` yet.**
   - Container Apps needs a container image if Container Apps is chosen.
3. **Frontend environment wiring.**
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
2. **Backend host.**
   - Container Apps vs. App Service.
   - Prepare options and tradeoffs; do not author the final decision text.
3. **Health/CORS implementation details.**
   - Likely small enough to implement from task 13 after the maintainer accepts
     the approach.
   - Decision points: one `/health` endpoint vs. separate `/live`/`/ready`;
     exact CORS parsing format; whether health should use `Depends(get_db)` or
     direct session creation.
4. **Lockdown strategy.**
   - Supabase app auth only vs. Azure Static Web Apps password protection vs.
     SWA auth routes vs. backend ingress restrictions.
5. **Error reporting.**
   - Application Insights vs. Sentry vs. defer.

**Suggested fresh-session order.**

1. Run `git status --short` and inspect current uncommitted docs changes.
2. Read `AGENTS.md`, `docs/ai-collaboration.md`, `docs/decisions.md`, and
   `docs/plan.md`.
3. Resolve the decision-storage confusion before adding new decision text.
4. For task 13, prepare a decision worksheet/options summary for the maintainer:
   DB-backed `/health`, configurable `CORS_ORIGINS`, tests, and `.env.example`
   updates.
5. After the maintainer accepts the task 13 approach, implement only that slice:
   - `app/config.py`: add CORS origins setting.
   - `app/main.py`: use configured CORS origins and make `/health` query DB.
   - `.env.example`: document `CORS_ORIGINS`.
   - tests: add focused coverage for health success/failure and CORS config if
     practical.
6. Run backend tests.
7. Stop and do the learning checkout before moving to Dockerfile or Azure
   workflow work.

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

- Dockerfile.
- GitHub Actions deployment workflows.
- Azure resource creation.
- Demo seed data.
- README screenshots.
- Search endpoint, session-close endpoint, FSRS weights, and ingestion pipeline.
