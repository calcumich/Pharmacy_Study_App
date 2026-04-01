-- Migration 002: User study tables — srs_state, study_sessions, flashcard_state
-- Depends on 001_core_schema.sql.
-- NOTE: users are managed by Supabase Auth. The auth.users table is referenced
-- here but not created — Supabase provisions it automatically.

-- ── Enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE srs_card_state AS ENUM ('new', 'learning', 'review', 'relearning');

-- ── srs_state ─────────────────────────────────────────────────────────────────
-- One row per (user_id, drug_id). Upserted on each review — not append-only.
-- FSRS algorithm fields; see docs/schema.md for field semantics.
-- srs_data JSONB is a safety column: extend here first if FSRS algorithm evolves.

CREATE TABLE srs_state (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL,   -- references auth.users (Supabase-managed)
    drug_id       UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,

    -- FSRS typed fields
    stability     FLOAT,
    difficulty    FLOAT,
    state         srs_card_state NOT NULL DEFAULT 'new',
    due_date      TIMESTAMPTZ,        -- indexed; SRS queue queries filter on this
    last_review   TIMESTAMPTZ,
    review_count  INT NOT NULL DEFAULT 0,

    -- Safety column for algorithm evolution — extend here before adding typed columns
    srs_data      JSONB NOT NULL DEFAULT '{}',

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, drug_id)
);

CREATE INDEX idx_srs_state_user_id  ON srs_state(user_id);
CREATE INDEX idx_srs_state_due_date ON srs_state(due_date);  -- SRS queue range queries

-- ── study_sessions ────────────────────────────────────────────────────────────
-- Append-only history log. Do not add UPDATE logic.
-- To "cancel" or amend a session, insert a correction row.

CREATE TABLE study_sessions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,               -- null until session closes
    drug_ids_studied    JSONB NOT NULL DEFAULT '[]',  -- array of drug UUIDs
    session_metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_study_sessions_user_id    ON study_sessions(user_id);
CREATE INDEX idx_study_sessions_started_at ON study_sessions(started_at);

-- ── flashcard_state ───────────────────────────────────────────────────────────
-- Per-user, per-drug, per-attribute-type state (buried, flagged, user notes).
-- Unique constraint enforced at DB level — application should UPSERT.

CREATE TABLE flashcard_state (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL,
    drug_id             UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    attribute_type_id   UUID NOT NULL REFERENCES attribute_types(id) ON DELETE CASCADE,
    is_buried           BOOLEAN NOT NULL DEFAULT FALSE,
    is_flagged          BOOLEAN NOT NULL DEFAULT FALSE,
    user_note           TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, drug_id, attribute_type_id)
);

CREATE INDEX idx_flashcard_state_user_id ON flashcard_state(user_id);
