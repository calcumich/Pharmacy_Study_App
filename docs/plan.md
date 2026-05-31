# Development Plan

## How to use this document

Work through tasks in order within each phase — later tasks build on earlier ones.
When you start a task, change `[ ]` to `[~]`. When it is done, change it to `[x]`
and add a one-line note under **Done** describing what was built or decided.

At the end of a session, update CLAUDE.md if any architectural decisions were made.

---

## Status key

- `[ ]` not started
- `[~]` in progress
- `[x]` done

---

## Phase 1 — Backend completeness

### [x] 1. Write endpoints + FSRS-5 scheduling

**Done:** `POST /study/sessions`, `POST /study/review`, `GET /study/queue` added to
`app/routers/study.py`. Pure FSRS-5 algorithm lives in `app/services/fsrs.py`.
30 unit tests in `tests/test_unit_fsrs.py`. `user_id` comes from request body with
TODO comments marking the JWT swap point.

---

### [x] 2. Smoke tests for write endpoints

**Done:** `tests/test_smoke_write.py` (5 tests) and `tests/conftest.py` added.
`client` fixture moved from `test_smoke_api.py` to `conftest.py` so both smoke
files share it. Fixed a bug in `GET /study/queue`: `learning` and `relearning`
state cards now always surface in the queue regardless of `due_date`, so rating=1
(Again) puts a card back into the active session immediately. All 61 tests pass.

---

### [x] 3. PATCH /study/flashcard-state

**Done:** `PATCH /study/flashcard-state/{drug_id}/{attribute_type_id}` added to
`app/routers/study.py`. `FlashcardStateUpdate` + `FlashcardStateResponse` schemas
added to `app/schemas/study.py`. Non-None-only conflict-update set ensures patching
one field never resets the others. Re-fetches after upsert to return authoritative
DB state. 2 unit tests in `tests/test_unit_flashcard_state.py`; 2 smoke tests
appended to `tests/test_smoke_write.py` covering the conflict-preserve path and
`user_note`. All 65 tests pass.

---

## Phase 2 — Frontend wiring

### [x] 4. Wire frontend to real backend

**Done:** `post<T>` helper + `createSession`, `submitReview`, `getQueue` added to
`client.ts`. Six new TypeScript interfaces added to `types/api.ts`. Write functions
re-exported from `index.ts` directly from the real client (mock has no write ops).
`App.tsx` creates a session on flashcard study start and passes `sessionId`/`userId`
to `FlashcardView`. `FlashcardView` shows Again/Hard/Good/Easy rating buttons after
reveal; clicking a rating calls `POST /study/review` then advances the card. Skip
button retained for pre-reveal navigation. `VITE_USE_MOCK=false`.

**Goal (archived):** Replace the static mock with live API calls. The app should work
end-to-end against a running backend.

**Context:**
- `frontend/.env` has `VITE_USE_MOCK=true`. Flipping it to `false` activates
  `src/api/client.ts` instead of `src/api/mock.ts`.
- `client.ts` already has the five read functions. It needs three write functions.
- `src/types/api.ts` needs matching TypeScript interfaces for the new schemas.
- `App.tsx:startStudy()` (line 131) builds cards from `getDrug()` calls but never
  calls `createSession()`. When in flashcard mode it should create a session and
  hold the `session_id` in state for attaching to reviews.
- `FlashcardView.tsx` renders cards but never calls `submitReview()`. It needs
  rating buttons (Again / Hard / Good / Easy) wired to `POST /study/review`.
- A hardcoded `user_id` UUID is fine for now; it will be replaced when auth lands.

**Steps:**
1. In `frontend/src/types/api.ts` add interfaces:
   `SessionCreate`, `SessionResponse`, `ReviewRequest`, `ReviewResponse`,
   `QueueItem`, `QueueResponse`, `FlashcardStateUpdate`, `FlashcardStateResponse`.
   Mirror the Pydantic schemas exactly (snake_case field names).
2. In `frontend/src/api/client.ts` add:
   - `createSession(body: SessionCreate): Promise<SessionResponse>`
   - `submitReview(body: ReviewRequest): Promise<ReviewResponse>`
   - `getQueue(userId: string, drugIds?: string[], limit?: number): Promise<QueueResponse>`
   A generic `post<T>` helper (matching the existing `get<T>`) will keep this tidy.
3. In `App.tsx`:
   - Add `sessionId: string | null` to state.
   - In `startStudy()`, call `createSession()` before entering study mode and store
     the returned `session_id`.
   - Pass `sessionId` down to `FlashcardView` as a prop.
4. In `FlashcardView.tsx`:
   - Add a `HARDCODED_USER_ID` constant at the top with a comment:
     `// TODO: replace with user identity from auth context`.
   - When the user flips a card, show four rating buttons (Again 1 / Hard 2 / Good 3 / Easy 4).
   - On rating click, call `submitReview()` with `user_id`, `drug_id`,
     `attribute_type_id`, and `rating`. Disable buttons until the request resolves.
   - Advance to the next card after the response arrives.
5. Flip `frontend/.env` to `VITE_USE_MOCK=false` and manually verify the full
   flow: browse → drugs → configure → flashcard study → submit a rating.

**Files to touch:** `frontend/src/types/api.ts`, `frontend/src/api/client.ts`,
`frontend/src/App.tsx`, `frontend/src/components/FlashcardView.tsx`,
`frontend/.env`.

---

## Phase 3 — Auth

### [x] 5. Auth groundwork (Supabase JWT)

**Done:** `app/dependencies/auth.py` created with `get_current_user` that decodes
Supabase HS256 JWTs via `python-jose`. `user_id` removed from `SessionCreate`,
`ReviewRequest`, and `FlashcardStateUpdate` schemas. All four write/queue endpoints
now use `Depends(get_current_user)`. Tests use `app.dependency_overrides` in
`conftest.py` — no real JWT needed in tests. `SUPABASE_JWT_SECRET` env var required
in production; defaults to `""` in development (deploy will 401 without it set).

**Goal (archived):** Replace the `user_id` request-body field with a proper JWT dependency so
every user-scoped endpoint authenticates automatically.

**Context:**
- All `user_id` fields in `ReviewRequest` and `SessionCreate` have TODO comments
  pointing here.
- Supabase issues standard JWTs; the `sub` claim is the user's UUID.
- The JWT secret is in the Supabase project settings (API → JWT Secret).
- Do not implement custom auth — just decode the Supabase-issued token.

**Steps:**
1. Add `python-jose[cryptography]` to `pyproject.toml` dependencies.
2. Add `supabase_jwt_secret: str` to `app/config.py` (reads from env var
   `SUPABASE_JWT_SECRET`).
3. Create `app/dependencies/auth.py` with a single function
   `get_current_user(token: str = Depends(oauth2_scheme)) -> uuid.UUID` that:
   - Decodes the Bearer JWT using `jose.jwt.decode`.
   - Returns the `sub` claim as a UUID.
   - Raises `HTTPException(401)` on any failure.
4. Remove `user_id` from `ReviewRequest` and `SessionCreate` schemas.
5. Update `POST /study/sessions`, `POST /study/review`, and
   `PATCH /study/flashcard-state` to accept
   `user_id: uuid.UUID = Depends(get_current_user)` instead of reading it from
   the body.
6. Update the `GET /study/queue` `user_id` query param to also use the dependency.
7. Update `tests/test_smoke_write.py` to pass a valid test JWT (or mock the
   dependency with `app.dependency_overrides`).

**Files to touch:** `pyproject.toml`, `app/config.py`,
`app/dependencies/auth.py` (new), `app/routers/study.py`, `app/schemas/study.py`,
`tests/test_smoke_write.py`.

---

### [x] 6. Frontend: Wire Supabase Auth

**Done:** `@supabase/supabase-js` installed. `src/lib/supabase.ts` initialises the
client from `VITE_SUPABASE_URL`/`VITE_PUBLISHABLE_KEY`. `client.ts` gained a
module-level `_token` variable + `setAuthToken()` export; both `get<T>` and `post<T>`
attach `Authorization: Bearer` when the token is set; `getQueue` no longer sends a
`user_id` query param. `SessionCreate` and `ReviewRequest` in `types/api.ts` had
`user_id` removed (backend reads identity from JWT sub claim). `App.tsx` replaced
`HARDCODED_USER_ID` with Supabase session state — shows a loading screen on init,
a login form when unauthenticated, and the main app once logged in; mock mode bypasses
the auth gate entirely. `FlashcardView` dropped the `userId` prop and the stale
`user_id` field in `submitReview`. `frontend/.env.example` created; `frontend/.env`
updated with placeholder Supabase vars. Missing `src/vite-env.d.ts` created to fix
pre-existing `import.meta.env` type errors; build is clean.

**Goal:** Replace `HARDCODED_USER_ID` in the frontend with a real Supabase session,
attach `Authorization: Bearer <token>` to every API call, and show a login screen
when no session exists.

**Context:**
- Task 5 wired backend JWT validation — the backend now reads `user_id` from the JWT
  `sub` claim, not from request bodies. `user_id` was removed from `SessionCreate`,
  `ReviewRequest`, `FlashcardStateUpdate`, and the `GET /study/queue` query param.
- `frontend/src/types/api.ts` is stale: `SessionCreate` and `ReviewRequest` still
  carry a `user_id` field that the backend no longer accepts.
- `App.tsx:17` has `const HARDCODED_USER_ID = '...'` passed to `createSession` and
  forwarded as a prop to `FlashcardView`.
- `FlashcardView.tsx:83` accepts `userId: string` as a prop and passes it to
  `submitReview` — this field is now redundant.
- `client.ts` `get<T>` and `post<T>` helpers don't attach any `Authorization` header.
- `client.ts:getQueue` passes `user_id` as a query param — backend now ignores it,
  so the param should be removed from the call.
- Do not implement custom auth. No backend changes.

**Steps:**
1. `npm install @supabase/supabase-js` — add to `frontend/package.json`.
2. Create `frontend/src/lib/supabase.ts`:
   - Initialise `createClient(VITE_SUPABASE_URL, VITE_PUBLISHABLE_KEY)` and export
     as `supabase`.
3. Update `frontend/src/api/client.ts`:
   - Add `let _token: string | null = null` and `export function setAuthToken(t: string | null)`.
   - In `get<T>`: add `Authorization: Bearer ${_token}` header when `_token` is set.
   - In `post<T>`: same.
   - Remove `userId: string` param from `getQueue`; drop the `user_id` query param.
4. Update `frontend/src/types/api.ts`:
   - Remove `user_id` from `SessionCreate` and `ReviewRequest`.
5. Update `frontend/src/App.tsx`:
   - Add `session: Session | null` state (from `@supabase/supabase-js`).
   - On mount, call `supabase.auth.getSession()` to restore an existing session and
     subscribe to `supabase.auth.onAuthStateChange`; on each change call
     `setAuthToken(session?.access_token ?? null)` and update `session` state.
   - Render a centered email/password login form (call
     `supabase.auth.signInWithPassword`) when `session === null`.
   - Remove `HARDCODED_USER_ID`; remove `user_id` from the `createSession` call.
   - Remove `userId` prop from `<FlashcardView>`.
6. Update `frontend/src/components/FlashcardView.tsx`:
   - Remove `userId` from `Props`.
   - Remove `user_id` from the `submitReview` call.
7. Add `VITE_SUPABASE_URL` and `VITE_PUBLISHABLE_KEY` to `frontend/.env.example`
   (create the file) and to `frontend/.env` as placeholders.

**Files to touch:** `frontend/package.json`, `frontend/src/lib/supabase.ts` (new),
`frontend/src/api/client.ts`, `frontend/src/types/api.ts`,
`frontend/src/App.tsx`, `frontend/src/components/FlashcardView.tsx`,
`frontend/.env.example` (new), `frontend/.env`.

---

## Phase 4 — Correctness & core UX (NEW — promoted ahead of Phase 5)

These were uncovered during the 2026-04-24 review. They sit ahead of the
quality-of-life work because they fix actual bugs or close gaps in the app's
core promise (spaced repetition).

### [x] 10. Make flashcards SRS-driven + fix DDI rendering

**Done:** `App.tsx::startStudy` now fetches drug details, `/study/queue`, and
relational data from `/study/table` in parallel during flashcard setup. Cards
are sorted so drugs that appear in the SRS queue come first, in queue order
(most overdue first); never-reviewed drugs follow. DDI cards are populated from
the table response indexed by `drug_id`, fixing the silent
`getCardContent(...) → []` regression. `FlashcardView` shows a state badge
(`new` / `learning` / `relearning` / `review`) above each card and, after a
rating, briefly displays "Next review in N days · stability X.X" using the
`ReviewResponse.due_date` and `stability` before auto-advancing. Frontend
builds clean; 69 backend tests still pass (one pre-existing auth-mock failure
on master is unrelated).

**Goal (archived):** The flashcard study path currently ignores `/study/queue`
and builds a static drug × attribute cross-product. DDI cards also render empty
because `getDrug()` returns no interaction data. Together: the app advertises
spaced repetition but doesn't actually deliver it, and one of the four card
shapes is broken.

**Context:**
- `frontend/src/components/FlashcardView.tsx::getCardContent` (line 70) returns
  `[]` for `at.slug === 'ddis'`. There is no path that loads interactions.
- `frontend/src/App.tsx::startStudy` (line 212) calls `getDrug()` per drug and
  flatMaps drug × attribute. It never calls `getQueue()`.
- `/study/queue` returns drug-level SRS state ordered by `due_date` ASC (most
  overdue first); learning/relearning cards always surface. This is the right
  ordering signal for cards.
- SRS state is per-(user, drug), not per-(user, drug, attribute) — the queue
  tells us which **drugs** are due; we still expand to (drug × attribute) cards
  on the client.

**Steps:**
1. In `App.tsx::startStudy`, after `createSession`, fetch in parallel:
   - `Promise.all(drugIds.map(getDrug))` (existing)
   - `getQueue(drugIds, 200)` (new — graceful fallback to `{items: []}` on error)
   - `getTable(drugIds, relationalAtIds)` only if any selected attribute has
     `shape === 'relational'`
2. Index the queue by `drug_id` to get an "due rank". Sort cards: cards whose
   drug is in the queue come first in queue order; rest follow original order.
3. Pass DDI data (indexed by drug_id) and queue items down to `FlashcardView`.
4. In `FlashcardView`, replace the `ddis` branch in `getCardContent` to look
   up DDI data from the prop. Add a small "Due" / "New" / "Learning" badge
   sourced from the queue map.
5. After `submitReview` resolves, briefly show the new `due_date` (e.g.
   "Next review in 3 days") before advancing — the response already carries it.

**Files to touch:** `frontend/src/App.tsx`,
`frontend/src/components/FlashcardView.tsx`, `frontend/src/types/api.ts`
(only if a new prop type is needed).

---

### [x] 11. Async-safe JWKS fetching

**Done:** `app/dependencies/auth.py` rewritten so `_fetch_jwks` and
`_decode_supabase_token` are `async`; JWKS retrieval now uses
`httpx.AsyncClient(timeout=5)` instead of `urllib.request.urlopen`. Added an
`asyncio.Lock` with double-checked caching so a cold start under concurrent
load only triggers one upstream JWKS fetch. `get_current_user` awaits the
helper and now traps `httpx.HTTPError` in addition to `JWTError` /
`RuntimeError` / `ValueError`. `httpx>=0.28` promoted from dev-only to a
runtime dependency in `pyproject.toml`. `tests/test_unit_auth.py` updated:
helper tests are now `@pytest.mark.asyncio`, `_fetch_jwks` monkeypatches are
async, and a pre-existing typo (`_algorithms` arg) that was failing on master
is fixed in passing. All 70 tests pass (was 69/70).

---

### [ ] 12. Sign-up form

**Goal:** New users currently can't onboard — `LoginForm` only signs in. Add a
toggle between sign-in and sign-up that calls `supabase.auth.signUp` and
explains the email-confirmation step.

**Files to touch:** `frontend/src/App.tsx` (or extract `LoginForm` to its own
file).

---

### [ ] 13. Real `/health` + configurable CORS

**Goal:** `/health` should `SELECT 1` so orchestrators detect DB outages.
`CORSMiddleware` should read allowed origins from settings instead of hardcoding
`localhost:5173`.

**Steps:**
1. `app/main.py` — `/health` runs a trivial DB query through `get_db`, returns
   `{db: "ok"}` or 503.
2. `app/config.py` — add `CORS_ORIGINS: list[str]` (default
   `["http://localhost:5173"]`); read from `CORS_ORIGINS` env var as a
   comma-separated list.
3. `app/main.py` — pass `settings.CORS_ORIGINS` to `CORSMiddleware`.
4. Update `.env.example`.

---

### [ ] 14. Visible error messages in the UI

**Goal:** `setError(String(e))` produces useless strings like `Error: API error
500: /study/review`. Surface a friendlier message and the underlying status.

**Files to touch:** `frontend/src/api/client.ts` (throw a typed error with
status + message body), `frontend/src/App.tsx`, `FlashcardView.tsx`.

---

## Phase 5 — Quality of life (was Phase 4)

### [ ] 15. Drug data ingestion pipeline

**Goal:** Establish a repeatable ingestion pipeline for expanding the drug
catalog without hand-editing seed data.

**Context:**
- The app's usefulness depends on having enough real drug/class/attribute data
  in Postgres to support browsing, comparison, search, and flashcard study.
- The repo has schema, migrations, and seed/bootstrap scripts, but no defined
  pipeline for importing larger datasets into the canonical schema.
- This work should map into the existing tables rather than introducing a
  parallel storage model.

**Steps:**
1. Choose an input format and source strategy (for example curated CSV/JSON
   files, transformed public datasets, or a staged import directory).
2. Define a normalization pass that maps source data into `drug_classes`,
   `drugs.attributes`, list-shape attribute tables, and canonical
   `drug_interactions` pairs.
3. Add an idempotent import command or script that validates rows, reports
   rejects clearly, and upserts into Postgres safely.
4. Add fixture-sized tests covering hierarchy import, attribute mapping, and
   duplicate-safe interaction loading.
5. Document the ingestion workflow and operator steps once the format is
   stable.

**Files to touch:** likely `scripts/`, backend import helpers, tests, and docs
once the ingestion design is chosen.

---

### [ ] 7. Drug search endpoint

**Goal:** `GET /drugs/search?q=` — full-text search backed by the existing
`tsvector` index on `drugs.search_vector`.


**Context:**
- The `search_vector` column is maintained by a DB trigger (see `docs/schema.md`).
  A GIN index already exists. Do not replace this with application-layer search.
- SQLAlchemy text-search syntax:
  `Drug.search_vector.op('@@')(func.plainto_tsquery('english', q))`

**Steps:**
1. Add `GET /drugs/search` to `app/routers/drugs.py`:
   - Query params: `q: str`, `class_id: UUID | None`, `limit: int = 20`.
   - Filter: `search_vector @@ plainto_tsquery('english', :q)`.
   - Optional `class_id` filter (exact match, not hierarchy — use a CTE if
     descendant traversal is needed).
   - Return `list[DrugSummary]`, ordered by relevance
     (`ts_rank(search_vector, query) DESC`).
2. Add a unit test mocking the DB session.

**Files to touch:** `app/routers/drugs.py`, `tests/test_unit_search.py` (new).

---

### [ ] 8. Session close endpoint

**Goal:** `PATCH /study/sessions/{session_id}/end` — sets `ended_at` to mark a
session complete.

**Context:**
- `docs/schema.md` says sessions are append-only and to insert a correction row
  rather than mutate history. Setting `ended_at` is lifecycle (not a correction),
  so a single targeted UPDATE is acceptable. Do not add any other UPDATE paths to
  `study_sessions`.
- This endpoint is low-priority; the rest of the app works without it.

**Steps:**
1. Add `PATCH /study/sessions/{session_id}/end` to `app/routers/study.py`.
   - Accept `user_id` (or `Depends(get_current_user)` if task 5 is done).
   - Only update `ended_at`; reject if already set (return 409 Conflict).
   - Return the updated `SessionResponse` with an added `ended_at` field.
2. Add `ended_at: datetime | None` to `SessionResponse` in `app/schemas/study.py`.

**Files to touch:** `app/routers/study.py`, `app/schemas/study.py`.

---

### [ ] 9. Per-user FSRS weights

**Goal:** Allow each user to have personalised FSRS weights rather than always
using `DEFAULT_W`.

**Context:**
- `app/services/fsrs.py` already accepts a `w: list[float]` parameter; it just
  defaults to `DEFAULT_W`. Plugging in per-user weights requires only loading them
  before calling `schedule()`.
- This needs a new DB table and Alembic migration.

**Steps:**
1. Add a migration `docs/db/migrations/004_user_fsrs_config.sql`:
   ```sql
   CREATE TABLE user_fsrs_config (
       user_id   UUID PRIMARY KEY,
       weights   JSONB NOT NULL DEFAULT '[]'::jsonb,
       updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   ```
2. Add `UserFsrsConfig` SQLAlchemy model to `app/models/study.py`.
3. Add `GET /study/fsrs-config` and `PATCH /study/fsrs-config` to
   `app/routers/study.py`.
   - GET returns the user's weights, or `DEFAULT_W` if no row exists.
   - PATCH validates that the submitted list has exactly 19 floats, then upserts.
4. In `submit_review`, load the user's weights before calling `fsrs_schedule()`.
5. Add an Alembic revision file in `alembic/versions/`.

**Files to touch:** `docs/db/migrations/004_user_fsrs_config.sql` (new),
`app/models/study.py`, `app/routers/study.py`, `app/schemas/study.py`,
`alembic/versions/<rev>_user_fsrs_config.py` (new).
