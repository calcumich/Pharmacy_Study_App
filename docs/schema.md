# Schema Design Rationale

This document captures the *why* behind the schema. The DDL migrations are the source
of truth for structure; this doc is the source of truth for intent. When Claude Code
makes decisions about queries, new columns, or new tables, it should check here first.

---

## Core domain model

A **drug** belongs to one or more **drug classes** (hierarchical). A drug has typed
**attributes** — some scalar (mechanism of action), some list-valued (indications,
ADRs), some relational (DDIs). A **user** studies drugs via flashcards; the SRS engine
tracks review state per drug per user.

---

## Table-by-table decisions

### `drug_classes`

Self-referential via `parent_id`. The hierarchy can be multiple levels deep
(e.g., Antibiotics → Beta-lactams → Penicillins).

**Always use recursive CTEs** to traverse descendants or ancestors. Do not walk the
tree in application code — the DB handles this correctly and efficiently with an index
on `parent_id`.

```sql
-- Example: all descendants of a class
WITH RECURSIVE descendants AS (
  SELECT id FROM drug_classes WHERE id = :root_id
  UNION ALL
  SELECT dc.id FROM drug_classes dc
  JOIN descendants d ON dc.parent_id = d.id
)
SELECT * FROM descendants;
```

### `drugs`

Two non-obvious columns:

**`attributes` (JSONB)**: Intentional escape hatch. Drug attributes vary significantly
by class — beta-blockers have selectivity, statins have potency rankings, etc. Rather
than a brittle EAV or a proliferation of nullable columns, irregular per-class fields
go here. This is not a TODO. Do not propose flattening it without a concrete schema
proposal and discussion.

**`search_vector` (tsvector)**: Maintained by a DB trigger that fires on INSERT/UPDATE
to `drugs`. Concatenates `name`, `generic_name`, and key JSONB text fields. Full-text
search queries hit this column via GIN index — no Elasticsearch, no application-layer
tokenization.

### `attribute_types`

Catalogue table. Every attribute kind that can appear on a drug (or drug-pair) must
have a row here before it's used anywhere. This is the single place where the
attribute's `shape` and `source_table` are defined.

**Three shapes:**

| Shape | Meaning | Source table |
|-------|---------|--------------|
| `scalar` | Single value, stored in `drugs.attributes` JSONB | `drugs` |
| `list` | Multiple values, each a row in a dedicated junction table | e.g. `drug_indications` |
| `relational` | Edge between two drugs with metadata | `drug_interactions` |

**`source_table` convention**: For `list` and `relational` shapes, `source_table`
names the actual table to query. Flashcard generation logic uses this to know where
to fetch values — it queries the catalogue rather than hardcoding a switch statement.

Do not add a new attribute kind by adding a column or a string literal somewhere. Add
a row to `attribute_types` first.

### `drug_indications`, `drug_adrs`, `drug_metabolism`

List-shape attribute tables. Each is a simple junction: `(drug_id, value_text)` plus
an optional `notes` field. Normalized out of `drugs` because a drug can have many of
each, and they need to be individually queryable (e.g., "all drugs indicated for
hypertension").

### `drug_interactions`

Relational-shape attribute. Models a DDI as an edge between two drugs.

**Canonical ordering**: `drug_a_id < drug_b_id` always. This is enforced by a CHECK
constraint and a unique index. The benefit: any given drug pair has exactly one row,
simplifying upserts and preventing duplicates.

**Implication for queries**: To find all interactions for drug X, query both directions:
```sql
WHERE drug_a_id = :x OR drug_b_id = :x
```

The `severity` column uses an enum (`minor`, `moderate`, `major`, `contraindicated`).
Additional metadata (mechanism of interaction, clinical significance notes) lives in a
`details` JSONB column on the interaction row.

### `srs_state`

One row per `(user_id, drug_id)`. Upserted on every review event — not append-only.
Stores current FSRS algorithm state.

**FSRS fields** (all typed columns, named per FSRS spec):
- `stability` (float): how long memory persists after review
- `difficulty` (float): inherent difficulty of the card
- `due_date` (timestamptz): when next review is scheduled — **indexed** for range queries
- `last_review` (timestamptz)
- `review_count` (int)
- `state` (enum: `new`, `learning`, `review`, `relearning`)

**`srs_data` (JSONB)**: Safety column alongside the typed fields. If the FSRS
algorithm evolves or we need to store additional state, extend `srs_data` first before
adding typed columns. This avoids repeated migrations during algorithm iteration.

Do not implement the SRS scheduling algorithm until the schema is stable and confirmed.

### `study_sessions`

Append-only log of study activity. Each row = one session start or end event.
Do not add UPDATE logic. If a session needs to be "cancelled" or amended, insert a
correction row — never mutate history.

Columns: `user_id`, `started_at`, `ended_at` (nullable until session closes),
`drug_ids_studied` (JSONB array), `session_metadata` (JSONB).

### `flashcard_state`

Tracks per-user, per-drug, per-attribute-type state (e.g., whether a card is buried,
flagged, or has a user note).

**Unique constraint on `(user_id, drug_id, attribute_type_id)`** — enforced at DB
level. Application code should upsert, not insert.

---

## Indexes worth knowing about

- `drugs.search_vector`: GIN index — full-text search
- `drug_classes.parent_id`: btree — recursive CTE traversal
- `drug_interactions(drug_a_id, drug_b_id)`: unique — canonical pair constraint
- `srs_state.due_date`: btree — SRS queue queries filter by due date range
- `srs_state(user_id, drug_id)`: unique — one row per pair

---

## What this schema intentionally does NOT have

- A Redis cache layer — not needed at this scale
- An Elasticsearch index — tsvector handles search
- A separate `flashcard_deck` or `deck` concept — study is drug-centric for now
- Frontend-facing view tables — kept in application layer until access patterns stabilize
