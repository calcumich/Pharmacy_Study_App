# Handover: Azure deployment

Paste this prompt into a fresh session to resume the Azure deployment thread.
Last updated 2026-06-01.

---

**Task: resume Azure deployment planning for the Pharmacy Study App.**

**Where we are (session ending 2026-06-01).**

The app is feature-complete enough to deploy. Auth (Supabase JWKS) and migrations
(consolidated to pure Alembic — decision #18) are done. The deployment target is
**Azure** (user has dev credits). The high-level architecture for the deploy is:

- **DB + Auth:** Supabase Cloud — stays. No move to Azure Postgres. Confirmed via
  decision #3 and the dev-mode-bypass setup in decision #17.
- **Backend:** Azure (Container Apps vs. App Service — *open*, recommendation was
  Container Apps for scale-to-zero).
- **Frontend:** Azure Static Web Apps vs. Vercel vs. Netlify — *being investigated
  in a separate session*. A handover prompt for that decision was issued earlier
  this session; the result should land as decision #19 in `docs/decisions.md`.

**Hard blockers for a public Azure deploy (still open):**

1. **Task 13 in `docs/plan.md`** — configurable CORS + real `/health` that exercises
   the DB. Required before going public (Container Apps health probes; CORS
   hardcoded to `localhost:5173` will reject the deployed frontend).
2. **No `Dockerfile` yet** — task 18 lists one but it hasn't been written.
   Container Apps needs a container image.
3. **`VITE_API_BASE_URL` wiring on the chosen frontend host** —
   `frontend/src/api/client.ts:14` already reads it, just needs to be set per-host.

**Nice-to-have, not blocking deploy itself:**

- Task 17 — seeded demo dataset (otherwise the demo URL shows an empty app).
- Task 19 — CI on PRs (green check, gates regressions).
- **Error reporting** — no plan.md task yet. Sentry-style server-side capture.
  Worth adding as a new task and possibly a decision (open vendor choice).

**Open decisions to make before/during this work:**

1. **Frontend host** — separate session in progress; check `docs/decisions.md` for
   a new #19 before starting.
2. **Backend on Container Apps vs. App Service** — not yet decided. Recommendation:
   Container Apps. Should land as the next decision after frontend host.
3. **Error reporting vendor** — Sentry vs. Azure Application Insights vs. nothing.
   Application Insights is the "stay in Azure" answer; Sentry is the "best DX"
   answer. Open.
4. **Schema visualization tool** — mentioned in decision #18 as a follow-up to
   keep the SQL-as-docs property the old `.sql` files provided. Not on the
   critical path.

**Suggested order of operations when resuming:**

1. Read `docs/decisions.md` start-to-finish — especially the most recent entries
   (#15, #17, #18, and whatever #19 turned into).
2. Read `docs/plan.md` Phase 4 (tasks 13, 14) and Phase 6 (tasks 18, 19, 20) —
   that's the active deployment surface.
3. Read `CLAUDE.md` for the codebase conventions and `README.md` for the
   high-level shape.
4. Knock out task 13 first (CORS + `/health`) — prerequisite for any public
   deploy, and small.
5. Write the Dockerfile (task 18 step 2).
6. Pick backend host (Container Apps recommended) and document as a new decision.
7. Pick error reporting vendor and add it as a new plan.md task.
8. Wire the Azure resources: Supabase Cloud Postgres → Container Apps backend →
   Static Web Apps (or whatever #19 lands on) frontend, with all the env vars
   from decision #17 set per-environment.
9. Run `alembic upgrade head` against Supabase Cloud Postgres (it's the canonical
   apply path now — decision #18).
10. Apply the demo seed (task 17) so the demo URL feels alive.
11. Update README with the live demo URL and screenshots (task 20).

**Important context the agent won't have:**

- Decision #17 sets up `AUTH_MODE=supabase|dev` (backend) and
  `VITE_AUTH_MODE=supabase|dev` (frontend) with an `APP_ENV` guardrail.
  Production deploys must run `AUTH_MODE=supabase` + `APP_ENV=production`; the
  guardrail rejects `AUTH_MODE=dev` outside `local`. All four env vars per
  environment need to be set in the host config.
- The frontend can also deploy in pure mock mode (`VITE_USE_MOCK=true`, decision
  #12) — useful if the backend isn't ready yet, keeps the GitHub demo link
  unbroken.
- Migration consolidation (decision #18) means `docs/db/migrations/` no longer
  exists. The apply path everywhere is `alembic upgrade head`. Don't recreate
  `.sql` files.
- `frontend/src/api/client.ts:14` reads `VITE_API_BASE_URL` with a localhost
  default — fine for the env-var-injection model on any static host.

**Out of scope for this resume task:**

- The frontend host decision itself (separate session).
- Anything pre-deployment in `docs/plan.md` (tasks 7, 8, 9, 14, 15 — those are
  unrelated feature work).
