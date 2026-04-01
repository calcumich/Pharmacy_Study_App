-- Migration 001: Core schema — drugs, classes, attributes, interactions
-- Run before 002 and 003.

-- ── Extensions ────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- supports GIN trigram index on drug names

-- ── Enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE attribute_shape AS ENUM ('scalar', 'list', 'relational');

CREATE TYPE interaction_severity AS ENUM ('minor', 'moderate', 'major', 'contraindicated');

-- ── drug_classes ──────────────────────────────────────────────────────────────
-- Self-referential hierarchy. Use recursive CTEs for traversal — see docs/schema.md.

CREATE TABLE drug_classes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    parent_id   UUID REFERENCES drug_classes(id) ON DELETE RESTRICT,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drug_classes_parent_id ON drug_classes(parent_id);

-- ── attribute_types ───────────────────────────────────────────────────────────
-- Catalogue table. All attribute kinds must exist here before use.
-- See docs/schema.md for shape/source_table conventions.

CREATE TABLE attribute_types (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug          TEXT NOT NULL UNIQUE,    -- machine identifier, used in queries
    label         TEXT NOT NULL,           -- human display label
    shape         attribute_shape NOT NULL,
    source_table  TEXT NOT NULL,           -- where values are stored (see docs/schema.md)
    is_system     BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── drugs ─────────────────────────────────────────────────────────────────────

CREATE TABLE drugs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    generic_name    TEXT,
    drug_class_id   UUID REFERENCES drug_classes(id) ON DELETE RESTRICT,
    attributes      JSONB NOT NULL DEFAULT '{}',  -- intentional; see docs/schema.md
    search_vector   TSVECTOR,                      -- maintained by trigger below
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drugs_search_vector ON drugs USING GIN(search_vector);
CREATE INDEX idx_drugs_drug_class_id ON drugs(drug_class_id);
CREATE INDEX idx_drugs_name_trgm     ON drugs USING GIN(name gin_trgm_ops);

-- Trigger: keep search_vector current on insert/update
CREATE OR REPLACE FUNCTION drugs_search_vector_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.generic_name, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.attributes->>'moa', '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_drugs_search_vector
    BEFORE INSERT OR UPDATE ON drugs
    FOR EACH ROW EXECUTE FUNCTION drugs_search_vector_update();

-- ── drug_indications ──────────────────────────────────────────────────────────

CREATE TABLE drug_indications (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id   UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    value     TEXT NOT NULL,
    notes     TEXT,
    UNIQUE (drug_id, value)
);

CREATE INDEX idx_drug_indications_drug_id ON drug_indications(drug_id);

-- ── drug_adrs ─────────────────────────────────────────────────────────────────

CREATE TABLE drug_adrs (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id   UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    value     TEXT NOT NULL,
    notes     TEXT,
    UNIQUE (drug_id, value)
);

CREATE INDEX idx_drug_adrs_drug_id ON drug_adrs(drug_id);

-- ── drug_metabolism ───────────────────────────────────────────────────────────

CREATE TABLE drug_metabolism (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id   UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    value     TEXT NOT NULL,   -- e.g. "CYP3A4 substrate", "hepatic first-pass"
    notes     TEXT,
    UNIQUE (drug_id, value)
);

CREATE INDEX idx_drug_metabolism_drug_id ON drug_metabolism(drug_id);

-- ── drug_interactions ─────────────────────────────────────────────────────────
-- Canonical ordering: drug_a_id < drug_b_id always.
-- To query all interactions for drug X: WHERE drug_a_id = X OR drug_b_id = X
-- See docs/schema.md for full rationale.

CREATE TABLE drug_interactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_a_id   UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    drug_b_id   UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    severity    interaction_severity NOT NULL,
    description TEXT,
    details     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Enforce canonical ordering
    CONSTRAINT chk_ddi_canonical_order CHECK (drug_a_id < drug_b_id),
    -- One row per drug pair
    UNIQUE (drug_a_id, drug_b_id)
);

CREATE INDEX idx_ddi_drug_a ON drug_interactions(drug_a_id);
CREATE INDEX idx_ddi_drug_b ON drug_interactions(drug_b_id);
