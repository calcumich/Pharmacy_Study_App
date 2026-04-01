-- Migration 003: Seed attribute_types catalogue
-- Depends on 001_core_schema.sql (attribute_types table must exist).
-- These rows encode the design decisions from docs/schema.md.
-- Flashcard generation queries this table rather than hardcoding a switch statement.

INSERT INTO attribute_types (slug, label, shape, source_table, is_system, display_order) VALUES
    ('moa',          'Mechanism of Action',     'scalar',      'drugs',               TRUE,  1),
    ('half_life',    'Half-life',               'scalar',      'drugs',               TRUE,  2),
    ('indications',  'Indications',             'list',        'drug_indications',    TRUE,  3),
    ('adrs',         'Adverse Drug Reactions',  'list',        'drug_adrs',           TRUE,  4),
    ('metabolism',   'Metabolism / CYP',        'list',        'drug_metabolism',     TRUE,  5),
    ('ddis',         'Major Drug Interactions', 'relational',  'drug_interactions',   TRUE,  6);

-- Notes on each row:
--
-- moa, half_life → shape=scalar, values stored in drugs.attributes JSONB under
--   the matching slug key. Flashcard generation reads drugs.attributes->>'moa'.
--
-- indications, adrs, metabolism → shape=list, values stored as rows in the
--   named source_table. Flashcard generation queries source_table WHERE drug_id=X.
--
-- ddis → shape=relational, values are drug_interactions rows. Flashcard generation
--   queries drug_interactions WHERE drug_a_id=X OR drug_b_id=X (both directions).
