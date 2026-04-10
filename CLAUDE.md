# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Pharmacy Study App — Claude Code Context

This is a spaced-repetition study tool for pharmacy students. Core concept: drugs have
structured attributes (mechanism, indications, interactions, etc.) that get surfaced as
flashcards. SRS state tracks per-user review history.

## Commands

### Backend

```bash
# Install dependencies (one-time / after pyproject.toml changes)
pip install -e ".[dev]"

# Run the dev server
uvicorn app.main:app --reload

# Run all tests
pytest

# Run a single test file
pytest tests/test_unit_tree_builder.py

# Run a single test by name
pytest tests/test_unit_tree_builder.py::test_parent_child_nesting

# Check that ORM models match the DB (should produce empty up/downgrade bodies)
alembic revision --autogenerate -m "check"

# Apply a new Alembic migration
alembic upgrade head
```

Tests in `tests/test_smoke_api.py` hit the real database via `TestClient`; all other test files use `app.dependency_overrides` to mock the DB session — no live DB required.

### Frontend

```bash
cd frontend
npm install        # one-time / after package.json changes
npm run dev        # Vite dev server at http://localhost:5173
npm run build      # type-check + production build
```

## Stack

- **Backend**: Python, **FastAPI** (decided — not TBD)
- **Frontend**: **React 18 + TypeScript + Vite** in `frontend/`; Tailwind CSS for styling
- **Database**: PostgreSQL via Supabase (standard Postgres; no Supabase-specific extensions besides Auth)
- **ORM / Migrations**: SQLAlchemy 2.0 (async) + Alembic
- **Auth**: Initially a PostgreSQL instance via Docker, later Supabase Auth — do not implement custom auth
- **Search**: tsvector full-text search via DB trigger — no Elasticsearch
- **Backend dependencies**: managed via `pyproject.toml`
- **Frontend dependencies**: managed via `frontend/package.json`

## Project structure

```
CLAUDE.md                      ← you are here
docs/
  schema.md                    ← full design rationale; read before touching schema
  db/
    migrations/
      001_core_schema.sql      ← drugs, classes, attributes, interactions
      002_user_study.sql       ← srs_state, study_sessions, flashcard_state
      003_seed_attribute_types.sql
app/
  main.py                      ← FastAPI entry point; registers routers + CORS
  config.py                    ← Settings (pydantic-settings, reads DATABASE_URL from env)
  db/
    session.py                 ← async engine + AsyncSessionLocal + get_db() dependency
  models/
    base.py                    ← DeclarativeBase
    drugs.py                   ← DrugClass, AttributeType, Drug, DrugIndication, DrugAdr, DrugMetabolism
    interactions.py            ← DrugInteraction
    study.py                   ← SrsState, StudySession, FlashcardState
  schemas/
    drug_classes.py            ← DrugClassNode (Pydantic response schema)
    drugs.py                   ← DrugSummary, DrugDetail
    attribute_types.py         ← AttributeTypeResponse
    study.py                   ← TableCell, TableResponse
  routers/
    drug_classes.py            ← GET /drug-classes, GET /drug-classes/{id}/drugs
    drugs.py                   ← GET /drugs/{id}
    attribute_types.py         ← GET /attribute-types
    study.py                   ← GET /study/table
frontend/
  index.html
  vite.config.ts
  tailwind.config.js
  .env                         ← VITE_USE_MOCK=true (dev default)
  .env.production              ← VITE_USE_MOCK=false
  src/
    main.tsx                   ← React entry point
    App.tsx                    ← wizard flow: browse → drugs → configure → study
    index.css                  ← Tailwind directives
    types/api.ts               ← TypeScript interfaces mirroring backend schemas
    api/
      client.ts                ← real fetch-based API client
      mock.ts                  ← static mock data (7 drugs, 2 class trees)
      index.ts                 ← re-exports client or mock based on VITE_USE_MOCK
    components/
      ClassBrowser.tsx         ← expandable class tree sidebar
      DrugSelector.tsx         ← checkbox list for drug selection
      AttributeSelector.tsx    ← checkbox list for attribute selection
      TableView.tsx            ← N×M comparison table
      FlashcardView.tsx        ← card flip with progress bar
alembic/
  env.py                       ← async Alembic env; reads DATABASE_URL from environment
  script.py.mako
  versions/                    ← generated revision files go here
alembic.ini                    ← sqlalchemy.url is a placeholder; env.py overrides it
pyproject.toml                 ← project dependencies
.env.example                   ← copy to .env and fill in DATABASE_URL
```

## Study modes

Two core study modes — both must be supported by the API:

- **Flashcard mode**: one drug × one attribute per card; SRS state tracked per
  (user, drug, attribute_type)
- **Table mode**: N drugs × M attributes rendered as a comparison grid; no SRS
  state, read-only. This is a first-class feature, not an afterthought.

The table endpoint should accept a list of drug_ids and a list of attribute_type_ids
and return a matrix of { drug_id, attribute_type_id, content } — suitable for
rendering a comparison table on the frontend.

## Core user flow (informs API design)

1. User browses drug class hierarchy and selects a class or subclass
2. User selects which attribute types to study
3. User chooses flashcard or table mode
4. App generates study material from that selection

The drug class hierarchy is self-referential (parent_id). API must support
fetching drugs by class including all descendant classes.

## Database — critical decisions

Full rationale in `docs/schema.md`. Short version for quick reference:

- `drugs.attributes` is **JSONB** — intentional escape hatch for per-class irregular fields. Do not flatten into typed columns without discussion.
- `drugs.search_vector` is a **tsvector** column maintained by a DB trigger. Do not replace with application-layer search.
- `drug_interactions` is **canonical-ordered**: always `drug_a_id < drug_b_id`. All queries must account for both directions.
- `drug_classes` is **self-referential** via `parent_id`. Use recursive CTEs for hierarchy traversal — no application-layer tree walking.
- `attribute_types` is a **catalogue table** — all attribute types must exist here before being used. Never hardcode an `attribute_type` string; query the catalogue.
- `srs_state` is **one row per (user_id, drug_id)**, upserted on each review. Not append-only.
- `study_sessions` is **append-only**. Do not add update logic.
- `flashcard_state` has a unique constraint on `(user_id, drug_id, attribute_type_id)`.

## SQLAlchemy model conventions

- All models use SQLAlchemy 2.0 `DeclarativeBase` + `Mapped` / `mapped_column` typed annotations.
- Postgres enums (`attribute_shape`, `interaction_severity`, `srs_card_state`) are declared with
  `create_type=False` — the types are created by the SQL migrations and must already exist in the DB.
  Corresponding Python `enum.Enum` classes live in the same model file for type safety.
- `user_id` in `srs_state`, `study_sessions`, and `flashcard_state` is a plain UUID column with no
  ORM FK — Supabase Auth manages the `auth.users` table outside this codebase.
- `drugs.search_vector` is included in the model for readability but is server-maintained by a DB
  trigger — never write to it from application code.

## Alembic

- `alembic.ini` has `sqlalchemy.url = placeholder`; `alembic/env.py` overrides this with
  `os.getenv("DATABASE_URL")` at runtime.
- Alembic uses an **async** engine (`async_engine_from_config` + `asyncpg`).
- `DATABASE_URL` must use the `postgresql+asyncpg://` scheme for both the app and Alembic.
- To apply SQL migrations manually and then stamp Alembic: run the `.sql` files via psql, then
  `alembic stamp head` so Alembic knows the schema is already in place.
- To verify models match the DB: `alembic revision --autogenerate -m "check"` should produce
  empty `upgrade()`/`downgrade()` bodies.

## Conventions

- Use **async SQLAlchemy** throughout — no sync sessions
- All schema changes via **Alembic migrations** — no manual DDL, no `CREATE TABLE` in application code
- Database connection from environment variable: `DATABASE_URL`
- FSRS algorithm fields live alongside a `jsonb srs_data` safety column — if FSRS evolves, extend `srs_data` first, then migrate typed columns

## Frontend conventions

- **Mock flag**: `VITE_USE_MOCK=true` in `frontend/.env` — swaps the entire API layer for static data.
  Set to `false` (or use `.env.production`) to point at the real backend. No other code changes needed.
- **CORS**: FastAPI allows `http://localhost:5173` (Vite dev server). Update `app/main.py` if the
  frontend port changes.
- **API client**: all API calls go through `src/api/index.ts`. Never call `fetch` directly from components.
- **Types**: `src/types/api.ts` is the single source of truth for TypeScript shapes. Keep in sync with
  `app/schemas/` when the backend changes.

## Out of scope — do not build until explicitly requested

- Redis or any caching layer
- Elasticsearch or external search index
- SRS algorithm implementation (schema must be stable first)
- Custom authentication
- Write endpoints (POST/PATCH/DELETE) — read-only API so far

## Updating this file

At the end of any session where significant architectural decisions are made, update
`CLAUDE.md` and `docs/schema.md` before closing out. A stale `CLAUDE.md` is worse
than none.
