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

**Alternatives considered.**
- **Django + Django REST Framework.** Batteries-included; built-in admin would
  have been useful for seeding/managing drug data.
- **Flask.** Lighter; familiar; would have worked.
- **Litestar / Starlette directly.** Litestar has nicer DI than FastAPI in
  some ways; Starlette is what FastAPI sits on.

**Why FastAPI.**
- Native async, which matters because the whole DB layer is async.
- Pydantic schemas double as request/response validation *and* the source of
  truth for the OpenAPI spec — the frontend's `types/api.ts` mirrors them by
  hand, but the option to codegen is there if the surface grows.
- Dependency injection (`Depends`) gave us a clean place to hang the JWT
  auth dependency without middleware.

**What we gave up.** Django's admin would have saved real time for content
management. We are paying for that absence in task 15 (drug ingestion
pipeline) and task 17 (seed dataset).

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
- Matches FastAPI's grain — no `run_in_threadpool` dances.
- The auth dependency fetches Supabase's JWKS over HTTP; that call is async
  with a shared lock for the cold-start path. A sync stack would have forced
  a thread offload or blocked the event loop.
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

## 13. Migrations: raw SQL as source of truth, Alembic alongside

**Decision.** Schema lives in `docs/db/migrations/*.sql` as raw, hand-written
DDL. Alembic is configured (async env + asyncpg) and used for verification
(`alembic revision --autogenerate -m "check"` should produce empty bodies)
but not as the primary migration mechanism.

**Alternatives considered.**
- **Alembic-only.** The standard SQLAlchemy approach. Migrations are
  Python; autogeneration is convenient.
- **A migration tool that lives outside Python entirely** (sqitch, goose,
  dbmate). Same idea as our SQL files but with a real apply-and-track tool.

**Why SQL-first.**
- The schema uses features Alembic's autogenerate handles poorly — DB
  triggers, `tsvector` columns, `CHECK` constraints, custom Postgres
  enums. Hand-rolled SQL is more honest about what the DB actually does.
- The SQL files double as documentation; a reader doesn't need to run
  Alembic to understand the shape of the DB.

**What we gave up.** The convenience of `alembic revision --autogenerate`
as the primary workflow. We *use* it as a drift-detector — if it
generates a non-empty migration, our models and DB are out of sync.

**Revisit-when.** The schema stops changing — at which point Alembic-only
becomes lower-friction. Or, conversely, when team size > 1 and the
"remember to update both" cost becomes real.

**Status.** Settled for the current pace of schema change.

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
