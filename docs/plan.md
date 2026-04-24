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

### [ ] 4. Wire frontend to real backend

**Goal:** Replace the static mock with live API calls. The app should work
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

### [ ] 5. Auth groundwork (Supabase JWT)

**Goal:** Replace the `user_id` request-body field with a proper JWT dependency so
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

## Phase 4 — Quality of life

### [ ] 6. Drug search endpoint

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

### [ ] 7. Session close endpoint

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

### [ ] 8. Per-user FSRS weights

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
