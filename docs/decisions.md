# Decisions

This document captures the architectural and product decisions that shape
this project — what we chose, what we passed on, and why. It is a reflection
document, not a marketing one: where a decision was a close call, a guess,
or a "good enough for now," that is recorded honestly.

For per-table schema rationale, see [`schema.md`](schema.md). For active work,
see [`plan.md`](plan.md). This file sits above both: it covers the choices
that shape the codebase as a whole.

**Status legend**

- **Settled** — decision is load-bearing; reversing it would mean a rewrite.
- **Revisit-when** — works for now, but a specific trigger should prompt a review.
- **Open** — actively undecided. Recorded so future-us remembers it was a choice.

---

## 1. Backend framework: FastAPI

**Decision.** Use FastAPI for the HTTP layer.

**Four main technologies considered.**

### FastAPI

**Shape.** Modern Python API framework built on Starlette, with Pydantic as
the validation/schema layer. Best fit when the backend is mostly an HTTP API
with typed request/response models, async I/O, and OpenAPI as a first-class
artifact.

**Why it fit this project.**
- Native async matches the SQLAlchemy 2.0 + asyncpg database layer.
- Pydantic schemas double as request/response validation *and* the source of
  truth for the OpenAPI spec. The frontend's `types/api.ts` mirrors them by
  hand today, but codegen is an easy next step if the surface grows.
- Dependency injection (`Depends`) gave us a clean place to hang the JWT auth
  dependency without middleware.
- It keeps the backend squarely in Python, which was an explicit learning goal
  for this project.

**Costs.**
- It is not batteries-included. Admin UI, background jobs, permissions,
  content-management workflows, and project structure are mostly choices we
  have to make ourselves.
- The async stack is powerful but has more footguns than a synchronous
  request/response app: session lifecycle, missing `await`s, and test setup
  all require attention.
- FastAPI's ecosystem is broad but uneven. There are many examples, but fewer
  mature conventions than Django has.

### Django + Django REST Framework

**Shape.** Full-stack Python web framework with ORM, admin, auth/session
machinery, forms, migrations, and a large ecosystem. DRF adds the API layer.
Best fit when the application benefits from a strong default structure and
server-side operational tools.

**Why it was tempting.**
- The Django admin would have saved real time for seeding, inspecting, and
  correcting drug data. For this app, that is the strongest argument Django
  had.
- Django's ORM, migrations, auth model, permissions patterns, and project
  layout are proven and well-documented.
- It is easier to hand future maintenance to another Python developer because
  Django conventions are older and more stable.
- If we later wanted server-rendered admin/content screens, Django would give
  us that without introducing a separate internal tool.

**Costs.**
- The framework brings a lot of machinery this app does not currently need:
  templates, forms, sessions, built-in auth flows, and a more monolithic
  project shape.
- Async support exists, but Django's deepest ecosystem habits are still
  synchronous. Since our DB layer is async, Django would either push us toward
  sync SQLAlchemy/Django ORM or force less common async patterns.
- DRF serializers plus Pydantic-style schemas would be another modeling layer
  to keep straight if we still wanted OpenAPI-driven frontend types.

### Flask

**Shape.** Minimal Python web framework. Best fit when the application is
small, mostly synchronous, and the developer wants to assemble the stack
piece by piece.

**Why it would have worked.**
- The app's backend surface is not huge. Flask could route these endpoints
  perfectly well.
- It is familiar, simple, and easy to understand at the file-by-file level.
- It avoids some FastAPI-specific magic around dependency injection and
  validation.

**Costs.**
- Almost every serious backend concern becomes an explicit integration choice:
  validation, OpenAPI generation, dependency injection, async handling, auth
  structure, and error conventions.
- Async Flask is possible, but it is not the natural grain of the framework in
  the way it is for FastAPI/Starlette.
- By the time we add schema validation, OpenAPI, typed responses, and async
  database access, we are rebuilding much of the reason FastAPI exists.

### ASP.NET Core (.NET)

**Shape.** Mature, high-performance web platform for C#. Best fit when we want
strong static typing across the backend, excellent tooling, first-class cloud
deployment, and long-term enterprise-grade maintainability.

**Why it deserved serious consideration.**
- ASP.NET Core is arguably the strongest non-Python option here: fast runtime,
  excellent built-in dependency injection, mature middleware, robust auth
  primitives, strong OpenAPI support, and first-class Azure deployment.
- The Azure story would have been cleaner. Container Apps, App Service, managed
  identity, Key Vault, Application Insights, and CI/CD all fit .NET naturally.
- Entity Framework Core would provide a cohesive ORM/migration story with good
  tooling and a lot of production mileage.
- C#'s type system is a real advantage for a backend with domain models,
  DTOs, service boundaries, and auth/user ownership rules.
- For portfolio purposes, a React + ASP.NET Core + Postgres app would be a very
  credible industry stack.

**Costs.**
- It would move the backend away from the user's explicit goal of learning
  more Python web development. That was the deciding factor.
- The SRS algorithm and data-ingestion work are naturally Python-shaped:
  Python is a better fit for quick algorithm experiments, scripts, notebooks,
  and data cleanup.
- Using .NET would likely split the learning surface: C#/.NET backend, Python
  scripts for ingestion/experimentation, TypeScript frontend. That is a lot of
  language/runtime context for a solo study app.
- The project would lose the clean Python-throughline from algorithm code to
  API services to backend tests.

**Related note: Litestar / Starlette directly.**

Starlette is the ASGI toolkit FastAPI sits on. Litestar is a
FastAPI-adjacent framework with a stronger emphasis on explicit application
structure, dependency injection, and plugin-style architecture.

**Why it was interesting.**
- Starlette directly would give maximum control with minimal framework layer.
- Litestar has some cleaner architectural ideas than FastAPI, especially around
  dependency injection and route/controller organization.
- Both fit an async SQLAlchemy stack naturally.

**Costs.**
- Starlette alone would mean manually adding validation, OpenAPI, and a higher
  level API structure.
- Litestar is capable, but the hiring/reviewer familiarity and tutorial
  surface are smaller than FastAPI's.
- Neither option materially changed the project outcome enough to justify
  choosing the less familiar path.

**Why FastAPI.**
- It hit the learning goal: Python web development, but with a modern typed
  API style rather than a purely traditional synchronous stack.
- It matched the async DB/auth implementation cleanly.
- It gave enough structure for validation, dependency injection, and OpenAPI
  without pulling in a full Django-sized application framework.
- It kept the SRS algorithm, ingestion scripts, backend services, and tests in
  one language ecosystem.

**What we gave up.**
- Django's admin would have saved real time for content management. We are
  paying for that absence in task 15 (drug ingestion pipeline) and task 17
  (seed dataset).
- ASP.NET Core would have made the Azure/backend deployment story more
  enterprise-standard and more strongly typed end to end. We passed on it not
  because it was weak, but because this project was also meant to build Python
  web-dev fluency.
- Flask would have been simpler at first, but less coherent once validation,
  OpenAPI, async DB access, and auth dependencies were added.
- Litestar/Starlette would have given more control, but less portfolio
  familiarity and less obvious upside for this app.

**Status.** Settled.

---

## 2. Async everywhere (SQLAlchemy 2.0 + asyncpg)

**Decision.** Async SQLAlchemy 2.0 sessions, `asyncpg` driver, async Alembic
env. No sync sessions anywhere in the codebase.

**Alternatives considered.**
- **Sync SQLAlchemy.** Simpler mental model; most tutorials use it; the app's
  throughput needs are tiny and sync would have been fine.
- **Mixed sync/async.** Sync ORM for migrations, async for the app.

**Why async.**
- This app is mostly I/O-bound: HTTP requests, Postgres queries, and occasional
  Supabase JWKS fetches. Async is a natural fit for that shape and avoids tying
  up one worker thread per waiting request.
- It matches FastAPI's grain and the selected DB driver (`asyncpg`), so the app
  can stay on one concurrency model instead of mixing async route handlers with
  sync DB/session code.
- It is not strictly required for this app's expected traffic. A synchronous
  SQLAlchemy stack would probably perform fine for a small study app, but async
  is the cleaner architectural fit once FastAPI + `asyncpg` + async JWKS are in
  the picture.
- It is a constraint we wanted to *learn* on a low-stakes project before
  hitting it on something where the cost of getting it wrong is higher.

**What we gave up.** A class of subtle bugs around forgetting `await`,
session lifecycle in tests, and library ecosystems that haven't fully caught
up. SQLAlchemy 2.0's typing is genuinely good but the docs lag the sync API.

**Status.** Settled.

---

## 3. Database: PostgreSQL via Supabase

**Decision.** Postgres is the only database. Hosted on Supabase. No
Supabase-specific extensions besides Auth.

**Alternatives considered.**
- **SQLite.** Would have made local dev and demo deploys trivial. Killed by
  the dependency on `tsvector`, JSONB, recursive CTEs over self-references,
  and `ON CONFLICT DO UPDATE` semantics we lean on for upserts.
- **Self-hosted Postgres on the deploy target.** More control; cheaper at
  scale; but adds an operational surface we explicitly do not want to own
  for a study app.
- **A different managed Postgres (Neon, RDS, Azure Postgres Flexible).**
  Any of these would work. Supabase was chosen because it ships Auth with
  the database — see decision #4.

**Why Supabase.**
- Auth and DB from the same vendor with one bill and one dashboard.
- Free tier covers a portfolio demo comfortably.
- Standard Postgres — we can lift-and-shift to any other managed Postgres
  if we need to. The auth coupling is the only real lock-in.

**Revisit-when.** Deploy target (task 18) is finalised. If we land on Azure
to use existing credits, moving the DB to Azure Postgres while keeping
Supabase *just* for Auth becomes a live option.

**Status.** Settled for now, with a clear exit path.

---

## 4. Auth: Supabase Auth, verified via JWKS

**Decision.** Supabase issues JWTs; the FastAPI backend verifies them
against Supabase's JWKS endpoint inside an async dependency
([`app/dependencies/auth.py`](../app/dependencies/auth.py)). `user_id` is
read from the `sub` claim, never from request bodies.

**Alternatives considered.**
- **Custom auth.** Email + password + bcrypt + our own session table. Explicitly
  ruled out by CLAUDE.md from the start — not a domain we want to own.
- **Auth0 / Clerk / WorkOS.** Strictly better DX than Supabase Auth for some
  flows. Killed by decision #3 — having auth in the same vendor as the DB
  was worth more than a nicer auth SDK.
- **HS256 shared-secret verification** (the original task-5 design). Simpler:
  one env var, no network call. We moved to JWKS (RS256) for two reasons:
  (a) Supabase rotates the signing key, and (b) a shared secret in
  application config is more blast-radius than a public key fetched at runtime.

**Why JWKS.**
- Key rotation works without redeploying.
- The public-key model is the right shape for a third-party-issued token.
- The async + cached implementation means JWKS is fetched once per
  process lifetime under normal conditions (one upstream call on cold start,
  serialised by an `asyncio.Lock`).

**What we gave up.** A small amount of complexity in the auth dependency
(JWKS cache, lock, HTTP failure paths) for properties we genuinely need.

**Status.** Settled.

---

## 5. SRS algorithm: FSRS-5, implemented in-repo

**Decision.** Implement the FSRS-5 algorithm from scratch in pure Python
([`app/services/fsrs.py`](../app/services/fsrs.py)) — no DB calls, no HTTP,
just `schedule(state, rating) -> new_state`.

**Alternatives considered.**
- **SM-2** (the classic Anki algorithm). Simpler; well-understood; would have
  been ~50 lines instead of ~300. Loses to FSRS-5 on retention accuracy in
  every public benchmark.
- **`py-fsrs`** or another off-the-shelf library. Would have saved a week.

**Why in-house.**
- The interesting engineering of this project *is* the SRS layer. Reaching
  for a library hides the part of the codebase a reviewer would most want
  to read.
- Pure-function design (no I/O inside `schedule()`) makes it trivially
  testable — 30 unit tests in `tests/test_unit_fsrs.py` exercise it without
  touching a DB or mocking anything.
- Per-user FSRS weights (task 9) are easier to plug in when we own the call
  signature.

**What we gave up.** Library updates as the FSRS spec evolves. The schema
hedges this with a `jsonb srs_data` column alongside the typed columns — if
FSRS-6 adds fields, we extend the JSON first, then promote to typed columns.

**Status.** Settled.

---

## 6. SRS granularity: state per (user, drug), not per (user, drug, attribute)

**Decision.** `srs_state` has one row per `(user_id, drug_id)`. A single drug
has one due date, one stability, one difficulty — even though a flashcard
session may surface multiple attribute cards for that drug.

**Alternatives considered.**
- **Per-(user, drug, attribute).** Each attribute card is scheduled
  independently. Closer to how Anki users typically structure decks; gives
  finer-grained "I keep forgetting the ADRs but I know the mechanism" signal.

**Why drug-level.**
- The pedagogical claim of the app is "you know *this drug*" — not "you know
  warfarin's mechanism in isolation." Drug-level state matches the claim.
- A simpler state table, an order of magnitude fewer rows, and a cleaner
  queue endpoint.
- `flashcard_state` is the per-(user, drug, attribute) escape hatch —
  user-written notes, hide/unhide — so the per-attribute axis is not lost,
  it is just not where SRS lives.

**Revisit-when.** User feedback indicates a drug is too coarse — e.g.,
"I learn fluoroquinolone names fine but tendon-rupture warnings never
stick." If that becomes a real pattern, we revisit and likely split into
per-(user, drug, attribute_group) rather than full per-attribute.

**Status.** Settled with a known revisit trigger.

---

## 7. Two study modes share one data model

**Decision.** Flashcard mode and table mode both read from the same
`drugs`, `attribute_types`, and `drug_*` tables. The only mode-specific
state is `srs_state` (flashcards only).

**Alternatives considered.**
- **Separate "deck" tables for flashcards.** Materialise card content into
  a `flashcards` table; table mode reads the underlying drugs. Mirrors how
  Anki models it.

**Why one model.**
- Table mode being a first-class study tool — not a quiz prep view — was
  decided early. Sharing the model keeps it that way structurally; you
  can't drift into "the real data lives in flashcards and table mode is
  a snapshot."
- New attribute types appear in both modes automatically.

**Status.** Settled.

---

## 8. Drug attributes: hybrid typed columns + JSONB escape hatch

**Decision.** Common attributes (`mechanism`, `indications`, `adrs`,
`metabolism`) are first-class typed columns or sub-tables. Irregular
per-class fields live in a `JSONB` column on `drugs`. Full per-table
rationale is in [`schema.md`](schema.md).

**Alternatives considered.**
- **Fully normalised EAV** (entity-attribute-value). Maximum flexibility,
  maximum query pain.
- **Fully typed columns.** A new nullable column every time a drug class
  has a quirk. Brittle; lots of `NULL`s; migration churn.
- **Fully JSONB.** Loses index-friendly queries on common fields.

**Why hybrid.**
- The 80/20 split between "every drug has this" and "only this class has
  this" is real in pharmacology. The schema reflects that.
- Typed columns are queryable, validatable, and visible in the OpenAPI
  spec. JSONB picks up the long tail.

**Revisit-when.** A field starts appearing in JSONB for >30% of drugs.
That is the signal to promote it to a typed column.

**Status.** Settled. See `schema.md` for the deeper "do not flatten
JSONB without a discussion" note.

---

## 9. Search: Postgres `tsvector`, trigger-maintained

**Decision.** Full-text search lives in a `tsvector` column on `drugs`,
populated by a DB trigger on INSERT/UPDATE, indexed with GIN. Queries use
`plainto_tsquery` and `ts_rank`. No application-layer search index.

**Alternatives considered.**
- **Elasticsearch / Meilisearch / Typesense.** Better relevance tuning,
  fuzzy matching, autocomplete out of the box. Adds an entire piece of
  infrastructure to operate.
- **Application-layer search.** Pull all drugs into memory and grep. Fine
  at 50 drugs; falls apart at 5,000.
- **App-managed `tsvector`** (recompute on save in Python). Risks drift
  if anyone writes a migration that updates `drugs` without going through
  the ORM.

**Why DB-side `tsvector`.**
- One-component architecture stays one-component.
- The trigger guarantees the index is always consistent with the row —
  no reconciliation job.
- Good enough for a drug catalog measured in thousands.

**Revisit-when.** Users start asking for typo tolerance, synonym handling
("MI" → "myocardial infarction"), or class-aware ranking. That is the
point where a real search engine earns its operational cost.

**Status.** Settled at current scale.

---

## 10. Drug interactions: canonical-ordered pairs

**Decision.** `drug_interactions` stores one row per pair with
`drug_a_id < drug_b_id`. All queries account for both directions.

**Alternatives considered.**
- **Two rows per pair** (one in each direction). Simpler queries;
  doubles the row count; introduces a consistency problem if the two rows
  drift.
- **Directed interactions** (drug A affects drug B differently from B → A).
  Real for a small subset (pharmacokinetic inducers vs. substrates) but
  the modeling burden across the whole table isn't worth it for the
  flashcard use case.

**Why canonical-ordered.**
- One source of truth per pair. The "both directions" cost lives in query
  helpers, not in the data model.
- Schema-enforced via a `CHECK` constraint.

**Status.** Settled. Per-table detail in `schema.md`.

---

## 11. Frontend: React 18 + Vite + TypeScript + Tailwind

**Decision.** SPA on Vite. React 18. TypeScript. Tailwind for styling.

**Alternatives considered.**
- **Next.js.** SSR, server components, file-based routing. Real value if
  this were content-heavy or SEO-sensitive; neither applies to a logged-in
  study tool.
- **SvelteKit.** Smaller bundle, more pleasant to write. Pure preference
  call — React won because it is the lingua franca for portfolio review.
- **HTMX + server-rendered Jinja from FastAPI.** Would have removed an
  entire client-side stack. Killed by the flashcard interaction — the
  reveal/rate/animate loop wants real client state.
- **CSS modules / vanilla CSS / Styled Components / shadcn.** Tailwind
  was the lowest-friction option for a solo developer iterating on layout.

**Status.** Settled.

---

## 12. Mock-mode API toggle (`VITE_USE_MOCK`)

**Decision.** A single env var swaps the entire API client for static
mock data. `index.ts` re-exports either `client.ts` or `mock.ts`.

**Alternatives considered.**
- **Storybook + MSW.** Mocks at the network layer; richer for component
  development. More setup than we needed.
- **No mock layer at all.** Always run against the backend.

**Why a single switch.**
- Frontend work can happen without spinning up Postgres + uvicorn.
- The static demo deploy (task 18) can ship in mock mode if the backend
  is unavailable, so the GitHub link is never broken.
- Keeps the mock honest — every API change has to update both files,
  which surfaces drift early.

**Status.** Settled. The mock surface needs to grow as the seed dataset
(task 17) grows.

---

## 13. ~~Migrations: raw SQL as source of truth, Alembic alongside~~

> **Superseded by #18 (2026-05-31).** The justification below assumed
> Alembic-only would mean autogenerated migrations that handle triggers and
> custom types poorly. In practice the Alembic revisions in
> `alembic/versions/` were hand-written `op.execute()` blocks containing the
> same SQL as the `.sql` files — so the readability argument was a wash and
> the duplication was pure cost. See #18 for the consolidation.

**~~Decision.~~** ~~Schema lives in `docs/db/migrations/*.sql` as raw, hand-written
DDL. Alembic is configured (async env + asyncpg) and used for verification
(`alembic revision --autogenerate -m "check"` should produce empty bodies)
but not as the primary migration mechanism.~~

**~~Alternatives considered.~~**
- **~~Alembic-only.~~** ~~The standard SQLAlchemy approach. Migrations are
  Python; autogeneration is convenient.~~
- **~~A migration tool that lives outside Python entirely~~** ~~(sqitch, goose,
  dbmate). Same idea as our SQL files but with a real apply-and-track tool.~~

**~~Why SQL-first.~~**
- ~~The schema uses features Alembic's autogenerate handles poorly — DB
  triggers, `tsvector` columns, `CHECK` constraints, custom Postgres
  enums. Hand-rolled SQL is more honest about what the DB actually does.~~
- ~~The SQL files double as documentation; a reader doesn't need to run
  Alembic to understand the shape of the DB.~~

**~~What we gave up.~~** ~~The convenience of `alembic revision --autogenerate`
as the primary workflow. We *use* it as a drift-detector — if it
generates a non-empty migration, our models and DB are out of sync.~~

**~~Revisit-when.~~** ~~The schema stops changing — at which point Alembic-only
becomes lower-friction. Or, conversely, when team size > 1 and the
"remember to update both" cost becomes real.~~

**Status.** Superseded by #18.

---

## 14. Plan-driven workflow (`docs/plan.md`)

**Decision.** Active work tracks as a checklist in `docs/plan.md` with
`[ ] / [~] / [x]` states and a Done note on completion. CLAUDE.md points
at it as the entry point for any new session.

**Alternatives considered.**
- **GitHub Issues.** Standard tool; better for collaboration; loses to
  in-repo for a solo project where conversation-with-Claude is the
  primary collaboration surface.
- **No tracking at all.** Tried briefly; produced rework.

**Why in-repo.**
- The plan is loaded into context with the rest of the docs every session.
- Git history of `plan.md` shows decision evolution in one place.

**Known cost.** Plan drift — task 12 (sign-up form) shipped before the
plan was updated and stayed `[ ]` for several commits. A "is the plan in
sync?" check at session start mitigates this but does not eliminate it.

**Status.** Settled.

---

## 15. Deployment target

**Decision.** Not yet made.

**Candidates on the table.**
- **Azure** (Container Apps + Static Web Apps; Postgres Flexible Server or
  keep Supabase). Existing dev credits make this attractive.
- **Fly.io.** Fastest path; Postgres in-region; modest free tier.
- **Render / Railway.** Similar to Fly; Render has a more generous free
  static-site offering.
- **GitHub Pages + Supabase Edge Functions.** Removes the backend host
  entirely. Loses if we want to keep the FastAPI app as the public
  artefact of the project — which we do.

**What needs to happen before deciding.**
- Task 13 (configurable CORS) — production demands a non-localhost origin.
- A clear picture of cold-start tolerance. A study tool where the first
  request takes 8 seconds is dead in the water for demo purposes.

**Status.** Open. Tracked as task 18 in `plan.md`.

---

## 16. README + inline Mermaid architecture diagram

**Decision.** Repo-level README at the root. Architecture diagram is
inline Mermaid in the README, not a separate image asset.

**Alternatives considered.**
- **Image (PNG/SVG) generated from draw.io / Excalidraw.** Renders
  identically everywhere; doesn't depend on GitHub's Mermaid renderer.
  Loses on maintainability — image assets drift from reality faster than
  text-based diagrams.
- **Separate `docs/architecture.md`.** Keep the README short. Reasonable
  if the diagram grows much beyond what it is today.

**Why inline Mermaid.**
- GitHub renders it natively in the README — the highest-traffic surface.
- It is plain text; it diffs cleanly; a future change to the architecture
  is visible in the PR.

**Revisit-when.** The diagram becomes too complex to read in a README, or
GitHub stops rendering Mermaid (unlikely but not impossible).

**Status.** Settled.

---

## 17. Environment modes: Supabase Cloud primary, Docker optional

**Decision.** Production and staging should use Supabase Cloud for both Auth
and Postgres. Local development should support two explicit modes:

- **Supabase auth mode.** The frontend shows the Supabase login flow; the
  backend verifies Supabase JWTs and derives `user_id` from the JWT `sub`
  claim. `DATABASE_URL` may point at Supabase Cloud Postgres or a local Docker
  Postgres, depending on what is being tested.
- **Dev auth mode.** The frontend bypasses the Supabase login screen; the
  backend does not require a bearer token and returns a fixed `DEV_USER_ID`
  from the auth dependency. This mode is for fast local development against
  disposable local data.

This should be controlled by separate frontend and backend flags:

- Backend: `AUTH_MODE=supabase|dev`
- Backend: `DEV_USER_ID=<uuid>` when `AUTH_MODE=dev`
- Frontend: `VITE_AUTH_MODE=supabase|dev`

The flags are intentionally separate because they control different layers.
`AUTH_MODE` decides how FastAPI produces the current user. `VITE_AUTH_MODE`
decides whether the React app requires a Supabase browser session before
rendering the application.

**Why this split.**

- It keeps production simple: Supabase Cloud owns identity and the primary
  Postgres database.
- It keeps local development fast: Docker Postgres plus a fixed test user can
  exercise real backend writes without requiring login or touching cloud data.
- It keeps integration testing possible: local dev can still run the real
  Supabase login flow when auth behavior is the thing being tested.
- It avoids making endpoints aware of the auth mode. Route handlers should
  continue to depend on `get_current_user`; the dependency should decide
  whether that user comes from a verified Supabase JWT or `DEV_USER_ID`.

**Docker's role.** Docker Postgres is an optional local development and test
database, not the primary architecture. It is useful for isolated resets,
schema/migration rehearsal, CI-style tests, and offline backend work. It should
not be presented as the default production-equivalent database when the target
architecture is Supabase Cloud Postgres.

**Guardrail.** `AUTH_MODE=dev` must be impossible to enable silently in
production or staging. Add an environment setting such as
`APP_ENV=local|staging|production` and fail application startup if
`AUTH_MODE=dev` while `APP_ENV` is not `local`.

**Documentation follow-up.** Update `.env.example`, frontend env examples, and
the README so they clearly distinguish:

- Supabase Cloud Auth + Supabase Cloud Postgres for staging/production.
- Supabase Auth + either cloud or Docker Postgres for integration-style local
  development.
- Dev auth bypass + Docker Postgres for fast local development.

**Status.** Settled, implementation pending.

---

## 18. Migrations: Alembic is the single source of truth (supersedes #13)

**Decision.** All schema changes live as Alembic revisions in
`alembic/versions/`. The `docs/db/migrations/*.sql` files are deleted. The
canonical apply path is `alembic upgrade head`, in every environment —
local, CI, staging, production.

**Why we reversed #13.**

When #13 was written, the assumption was that "Alembic-only" meant relying on
`alembic revision --autogenerate`, which handles Postgres features like
triggers, `tsvector` columns, and custom enums badly. That premise turned
out not to apply here: the Alembic revisions that were committed alongside
the `.sql` files were hand-written `op.execute()` blocks containing the
same DDL. Nobody used autogenerate for the load-bearing migrations. So #13
was paying the cost of duplication (two files to keep in sync, no clear
authority when they drifted, two paths to apply) without getting the
readability win it claimed — the SQL is just as readable inside an
`op.execute("""…""")` block.

**What we gave up.** A standalone, runner-free way to view the schema as
plain `.sql`. We accept that reading `alembic/versions/8d50f2cb30e1_initial_schema.py`
is the new "look at the schema" path. `docs/schema.md` remains the place
for design rationale (the *why* of each table) — the Alembic file is the
*what*.

**Why not a different tool** (sqitch, dbmate, Supabase CLI).
- Sqitch / dbmate solve the same problem Alembic already solves for us;
  adopting one would mean rewriting work that already exists.
- Supabase CLI (`supabase db push`) is on-platform tooling we may end up
  using anyway, but it locks the deploy pipeline to one vendor's CLI and
  abandons the async-Alembic env that's already wired into the codebase.
  Worth revisiting only if we adopt Supabase's broader local-dev tooling.

**Schema visualization.** The "SQL files double as documentation" argument
from #13 isn't entirely wrong — there's value in a quick visual on the
schema. The replacement is a dedicated visualization tool (e.g.,
`pg_dump --schema-only` piped to a diagram generator, dbdiagram.io, or
SchemaSpy) run on demand, not a parallel set of migration files committed
to the repo. Tool choice is open; not on the critical path.

**Consequences.**
- `docs/db/migrations/` folder removed.
- `CLAUDE.md`, `README.md`, and `docs/plan.md` updated to point at
  `alembic/versions/` only.
- `alembic revision --autogenerate -m "check"` retained as the model-vs-DB
  drift detector.

**Status.** Settled.

---

## 19. Frontend hosting: Azure Static Web Apps

**Decision.** Host the Vite frontend on Azure Static Web Apps. The backend
remains a separate FastAPI service, likely on Azure Container Apps per #15,
and the browser still talks directly to Supabase for auth. The frontend build
injects `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_PUBLISHABLE_KEY`,
`VITE_AUTH_MODE=supabase`, and either `VITE_USE_MOCK=false` for the real demo
or `VITE_USE_MOCK=true` for a backend-independent fallback demo.

**Alternatives considered.**
- **Vercel.** Best pure frontend developer experience for this app shape:
  Vite is essentially zero-config, GitHub deploys are polished, and preview
  deployments per PR are excellent. If the frontend were the main artefact, or
  if PR preview UX mattered more than platform consolidation, Vercel would be
  the likely pick.
- **Netlify.** Similar static-site fit to Vercel, with strong deploy previews,
  custom domains, automatic HTTPS, and long-standing SPA hosting support.
  It would work fine, but does not beat Vercel on DX or Azure on project goals.
- **Cloudflare Pages.** Technically very strong for a static SPA: generous free
  limits, preview deployments, custom domains, and global delivery. It is the
  best "cheap static hosting" answer, but it adds another platform without
  teaching the Azure deployment story this project wants to exercise.
- **GitHub Pages.** Simple and free, but weaker for environment management and
  deploy previews. It feels more like "publish files" than an application
  hosting target.

**Why Azure Static Web Apps.**
- The project already leans Azure for the backend, and using SWA keeps the live
  demo under one cloud story: Static Web Apps for the React bundle, Container
  Apps for FastAPI, Supabase for Auth/Postgres.
- The user's Azure dev credits and Azure resume gap are legitimate decision
  inputs. For a portfolio project, learning and demonstrating Azure deployment
  matters almost as much as raw hosting convenience.
- SWA fits the actual frontend: React 18 + Vite + TypeScript + Tailwind builds
  to static assets, with no SSR, ISR, edge functions, or server-side runtime.
- GitHub-based deploy on push to `main` is first-class, and SWA supports
  pull-request pre-production environments. Vercel is smoother here, but SWA is
  good enough for task 19's CI/PR workflow.
- SPA routing is not a blocker: add `staticwebapp.config.json` with
  `navigationFallback` rewriting to `/index.html`.
- Free tier is enough for a low-traffic portfolio demo: static hosting, SSL,
  custom domains, GitHub integration, and a small number of staging environments.
- The existing `VITE_USE_MOCK=true` path gives us an escape hatch: even if the
  Container Apps backend is asleep, broken, or intentionally paused, the public
  frontend can still stay live as a demo shell.

**What we gave up.**
- Vercel's cleaner frontend-first workflow and preview deployment ergonomics.
  For a team shipping frontend-heavy product work, that might matter more.
- Netlify's mature static-host workflow and visual review features.
- Cloudflare Pages' extremely generous static hosting limits and simple global
  delivery story.
- Some Azure-specific configuration overhead: SWA needs a small routing config,
  build env vars need to be wired through the Azure/GitHub deploy path, and the
  portal is heavier than Vercel or Netlify for a small SPA.

**Revisit-when.**
- SWA preview environments get in the way of the PR workflow after task 19.
- The frontend needs framework features SWA does not serve well, such as SSR or
  server-side rendering at the edge.
- Azure billing or quota behavior becomes more distracting than useful for a
  portfolio demo.
- The backend moves off Azure, removing the main reason to keep the frontend
  there.

**Status.** Settled for the live demo, with Vercel as the fallback if Azure
Static Web Apps creates more deployment friction than expected.

---

## 20. Deployment readiness: health check and CORS

This entry covers two small deployment-readiness choices. They can ship in one
PR because they both unblock cloud deployment, but they answer different
questions:

- **Health check:** how does the backend report whether it is usable?
- **CORS:** which browser origins may read responses from the backend API?

### 20a. Health endpoint

**Decision question.** What should `/health` prove?

**Context.** A custom `/health` endpoint may not be strictly required for the
backend to start on Azure, but it gives the host and maintainer a simple
readiness signal. For this app, a static process check is weak because the API
depends on Supabase Postgres. If the database is unreachable, the FastAPI
process may still be running, but the application is not useful.

**Options considered.**
- **Static process health.** Return 200 if the FastAPI process can serve the
  route. This is simple and avoids touching the database, but it does not catch
  database connectivity failures.
- **DB-backed readiness check.** Run a trivial query such as `SELECT 1` against
  the configured database and return 503 if it fails. This is a better signal
  for a database-backed API, but it means health probes can add small database
  load and DB outages will make `/health` fail.
- **Separate `/live` and `/ready`.** `/live` proves the process is running;
  `/ready` proves dependencies are reachable. This is operationally precise,
  but more surface area than this app needs for the first deploy.

**Recommended option.** Use one unauthenticated DB-backed `/health` endpoint for
now. Return minimal information, such as `{ "status": "ok", "db": "ok" }`, and
return 503 without leaking connection strings, exception details, table names,
or Supabase internals when the DB check fails. Revisit separate `/live` and
`/ready` endpoints if Azure health probes, uptime monitoring, or debugging needs
start pulling those concerns apart.

**Questions for the maintainer.**
- Can I explain the difference between "the process is running" and "the app is
  ready to serve useful traffic"?
- Am I comfortable with `/health` failing when Supabase Postgres is unavailable?
- What information is safe to return from a public health endpoint?
- What would make us split `/health` into `/live` and `/ready` later?

**My current understanding.** Health is a useful metric, and necessary for a lot
of the infrastructure that supports cloud deployments. It needs to exercise
minimal logic, and can be separated into liveness and readiness. If you ping the
DB, you need to think about things like the timeout period (you might favor short
timeouts so that a slow DB response doesn't trigger container restarts). Adding
authentication sounds appealing, but it might make it difficult for some
infrastructure to ping your containerized app. In a cloud-based environment, you
might see a container as functioning, but the app might be thrashing due to
memory issues, deadlocks, or infinite loops.

**Decision.** Combine liveness and readiness into a single `/health` check.
Exercise minimal `SELECT 1` query just to test the DB connectivity roundtrip. No
authentication at this time.

**Consequences.** Cannot distinguish between liveness and readiness. DB
connectivity could cause the `/health` check to fail.

**Reversal trigger.** Consider reconfiguration if we see things like DB timeouts
leading to issues with the health checks.

**Learning debt.** Unknown

**Status.** Decided

### 20b. Configurable CORS origins

**Decision question.** How should the backend decide which frontend origins are
allowed to call it from browser JavaScript?

**Context.** The frontend and backend will be served from different origins:
Azure Static Web Apps for the Vite/React bundle, and a separate Azure-hosted
FastAPI service for the API. Browsers enforce CORS before frontend JavaScript
can read cross-origin API responses. CORS is not backend authorization; the API
still depends on Supabase JWT validation for real access control.

Currently `app/main.py` hard-codes `allow_origins=["http://localhost:5173"]`,
which matches the local Vite dev server but will block the deployed frontend.

**Options considered.**
- **Hard-code each origin in code.** Simple for one local origin, but every
  staging, production, or preview URL change requires a code change and
  redeploy.
- **Allow all origins.** Easy during development, but too loose for an
  authenticated API and a bad production habit. It can also conflict with
  credentialed requests depending on middleware settings.
- **Environment-configured allow list.** Read explicit allowed origins from
  configuration, defaulting to the local Vite origin. This supports local,
  staging, and production without changing code.
- **Pattern-based origins.** Allow origins by regex or wildcard, such as a
  family of Azure Static Web Apps preview URLs. This can reduce config churn for
  preview environments, but it is easier to make too broad.

**Recommended option.** Use an explicit comma-separated `CORS_ORIGINS`
environment variable, defaulting to `http://localhost:5173`. Add the Azure
Static Web Apps origin when it exists. Revisit regex or wildcard support only if
Azure preview environments become a real workflow requirement.

**Questions for the maintainer.**
- Can I explain why CORS is browser-enforced and not a substitute for JWT auth?
- Which exact origins should be allowed for local development, staging, and
  production?
- Do we need pull-request preview frontend URLs to call a deployed backend, or
  can preview builds stay in mock mode for now?
- What would make a pattern-based allow list worth the added risk?

**My current understanding.** Misconfigured allow-origins will prevent the
user's browser from being able to exercise JavaScript that comes from a
different source. Because our backend will be a different origin, it needs to be
configured properly. I like the idea of being able to do both cloud and local
development for now, so a configurable option would be good. Regex feels like
overkill. CORS is configured on the backend, and allows only certain origins to
read responses from browser-based requests. Some simple requests may still be
sent without a preflight request, but the browser controls whether frontend
JavaScript can read the response. You can configure additional options which
will be returned in a preflight request that can put more granular restrictions
on what the client's browser will allow.

**Decision.** We'll use an environment variable-stored CSV for allowed origins.
Locally, those will be for the correct localhost port. In the cloud, those will
be configured for our frontend service.

**Consequences.** Need to maintain env variables in both local and cloud
settings. Any changes to allowed origins will need to be updated in the correct
places.

**Reversal trigger.** If we struggle to maintain environment variables properly in the cloud and local settings.

**Learning debt.** CORS always feels fuzzy. The additional headers that you
configure with CORS are beyond my understanding. It's also important to know
that this won't lock down your API; it just means that potentially malicious
sites cannot read API responses through a user's browser unless the backend
allows that origin.

**Status.** Decided.
---

## How to add to this document

When a non-trivial decision gets made:

1. Add a new numbered section here with: Decision, Alternatives considered,
   Why, What we gave up (if anything), Status.
2. Be honest about close calls and guesses. "We picked X because it was
   familiar" is a valid entry. "We picked X because it is objectively
   best" usually isn't.
3. If a decision in this doc later gets reversed, **do not delete the
   entry** — strike it through and add a "Superseded by #N" pointer. The
   reasoning that was wrong is as useful as the reasoning that was right.
4. (6/4/26) Follow the format described in `docs/ai-collaboration.md`.
